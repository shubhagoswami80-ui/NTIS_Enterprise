from __future__ import annotations

from typing import Any
import math
import numpy as np
import pandas as pd

FAST_SESSIONS = 3
CORE_SESSIONS = 5
STRUCTURAL_SESSIONS = 10


def _num(v: Any) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except Exception:
        return float("nan")


def _breadth(row: pd.Series) -> float:
    adv, dec, unchg = (_num(row.get(k)) for k in ("adv", "dec", "unchg"))
    if not all(math.isfinite(x) for x in (adv, dec)):
        return float("nan")
    total = sum(x for x in (adv, dec, unchg) if math.isfinite(x))
    return ((adv - dec) / total) * 100.0 if total > 0 else float("nan")


def _parse_buildup(v: Any) -> str:
    s = str(v or "").strip().upper().replace(" ", "_")
    return {
        "LB": "LONG_BUILDUP", "LONG_BUILDUP": "LONG_BUILDUP",
        "SB": "SHORT_BUILDUP", "SHORT_BUILDUP": "SHORT_BUILDUP",
        "LU": "LONG_UNWINDING", "LONG_UNWINDING": "LONG_UNWINDING",
        "SC": "SHORT_COVERING", "SHORT_COVERING": "SHORT_COVERING",
    }.get(s, s or "UNKNOWN")


def _flow_direction(price: float, oi: float, buildup: str) -> float:
    """Observable price/OI interpretation; never represents participant identity."""
    if math.isfinite(price) and math.isfinite(oi):
        if price > 0 and oi > 0: return 1.0
        if price > 0 and oi < 0: return 1.0
        if price < 0 and oi < 0: return -1.0
        if price < 0 and oi > 0: return -1.0
    return {
        "LONG_BUILDUP": 1.0, "SHORT_COVERING": 1.0,
        "SHORT_BUILDUP": -1.0, "LONG_UNWINDING": -1.0,
    }.get(buildup, 0.0)


def _sessions(history: pd.DataFrame) -> list[pd.Timestamp]:
    if history.empty:
        return []
    x = pd.to_datetime(history["observed_at"], errors="coerce").dropna()
    return sorted(x.dt.normalize().unique())


def _daily_latest(history: pd.DataFrame, limit: int = STRUCTURAL_SESSIONS) -> pd.DataFrame:
    h = history.copy()
    h["observed_at"] = pd.to_datetime(h["observed_at"], errors="coerce")
    h = h.dropna(subset=["observed_at", "sector"]).sort_values("observed_at")
    dates = _sessions(h)[-limit:]
    h = h[h["observed_at"].dt.normalize().isin(dates)]
    h["_session"] = h["observed_at"].dt.normalize()
    return (
        h.sort_values("observed_at")
         .groupby(["_session", "sector"], as_index=False, sort=False)
         .tail(1)
         .sort_values(["_session", "sector"])
         .reset_index(drop=True)
    )


def _rank_series(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce")
    return values.rank(method="average", pct=True, ascending=not higher_is_better) * 100.0


def _prepare_daily(history: pd.DataFrame) -> pd.DataFrame:
    d = _daily_latest(history)
    if d.empty:
        return d
    for c in ("price_chg", "volume_chg", "oi_chg", "rollover", "ce_oi_chg", "pe_oi_chg", "pe_ce_oi_chg"):
        d[c] = pd.to_numeric(d.get(c), errors="coerce")
    d["breadth"] = d.apply(_breadth, axis=1)
    d["flow_direction"] = d.apply(
        lambda r: _flow_direction(_num(r.get("price_chg")), _num(r.get("oi_chg")), _parse_buildup(r.get("buildup"))),
        axis=1,
    )
    d["price_rank"] = d.groupby("_session")["price_chg"].transform(lambda s: _rank_series(s))
    d["breadth_rank"] = d.groupby("_session")["breadth"].transform(lambda s: _rank_series(s))
    d["oi_rank"] = d.groupby("_session")["oi_chg"].transform(lambda s: _rank_series(s))
    d["volume_rank"] = d.groupby("_session")["volume_chg"].transform(lambda s: _rank_series(s))
    d["relative_score"] = (
        d["price_rank"].fillna(50) * 0.34
        + d["breadth_rank"].fillna(50) * 0.28
        + d["oi_rank"].fillna(50) * 0.14
        + d["volume_rank"].fillna(50) * 0.14
        + d["flow_direction"].map({1.0: 100.0, -1.0: 0.0, 0.0: 50.0}).fillna(50) * 0.10
    )
    return d


def _sector_history(daily: pd.DataFrame, sector: str) -> pd.DataFrame:
    return daily[daily["sector"].astype(str).str.strip() == sector].sort_values("_session").copy()


def _rank_trajectory(h: pd.DataFrame) -> tuple[float, float, list[float]]:
    """Return relative-leadership trajectory, not an absolute trading score.

    The trajectory is based on the cross-sectional relative score already built
    for each session. A rising trajectory means the sector is gaining leadership
    against its peer group; a falling trajectory means leadership is decaying.
    """
    if h.empty:
        return 0.0, 0.0, []
    ranks = pd.to_numeric(h["relative_score"], errors="coerce").dropna().tolist()
    if len(ranks) < 2:
        return 0.0, 0.0, ranks
    x = np.arange(len(ranks), dtype=float)
    slope = float(np.polyfit(x, np.asarray(ranks, dtype=float), 1)[0])
    diffs = np.diff(np.asarray(ranks, dtype=float))
    recent = diffs[-min(3, len(diffs)):]
    prior = diffs[-min(6, len(diffs)):-min(3, len(diffs))] if len(diffs) >= 4 else np.asarray([], dtype=float)
    recent_velocity = float(np.mean(recent)) if len(recent) else 0.0
    prior_velocity = float(np.mean(prior)) if len(prior) else recent_velocity
    acceleration = recent_velocity - prior_velocity
    return slope, acceleration, ranks


def _delta(h: pd.DataFrame, col: str, window: int) -> float:
    if len(h) <= window:
        return float("nan")
    a = _num(h.iloc[-1].get(col))
    b = _num(h.iloc[-window-1].get(col))
    return a - b if math.isfinite(a) and math.isfinite(b) else float("nan")


def _directional_ratio(h: pd.DataFrame, col: str, direction: str, window: int) -> float:
    if h.empty or col not in h.columns:
        return float("nan")
    x = pd.to_numeric(h[col], errors="coerce").dropna().tail(window)
    if x.empty:
        return float("nan")
    if direction == "INTO":
        return float((x > 0).mean() * 100.0)
    if direction == "OUT":
        return float((x < 0).mean() * 100.0)
    return float("nan")


def _structural_profile(h: pd.DataFrame, direction: str) -> dict[str, float]:
    return {
        "price_5_ratio": _directional_ratio(h, "price_chg", direction, CORE_SESSIONS),
        "price_10_ratio": _directional_ratio(h, "price_chg", direction, STRUCTURAL_SESSIONS),
        "breadth_5_ratio": _directional_ratio(h, "breadth", direction, CORE_SESSIONS),
        "breadth_10_ratio": _directional_ratio(h, "breadth", direction, STRUCTURAL_SESSIONS),
        "volume_5_ratio": _directional_ratio(h, "volume_chg", direction, CORE_SESSIONS),
        "volume_10_ratio": _directional_ratio(h, "volume_chg", direction, STRUCTURAL_SESSIONS),
        "oi_5_ratio": _directional_ratio(h, "oi_chg", direction, CORE_SESSIONS),
        "oi_10_ratio": _directional_ratio(h, "oi_chg", direction, STRUCTURAL_SESSIONS),
    }


def _opportunity_profile(row: dict[str, Any], trend: dict[str, Any], direction: str) -> dict[str, Any]:
    """Classify opportunity type separately from evidence strength.

    The purpose is discovery, not a hard confirmation gate.  A sector can be
    interesting because it is a leader, a recovery/reversal, or a deteriorating
    leader.  Missing secondary evidence lowers confirmation but does not erase
    the opportunity.
    """
    if direction == "NEUTRAL":
        return {
            "intraday_level": "NO CLEAR OPPORTUNITY",
            "swing_level": "NO CLEAR OPPORTUNITY",
            "intraday_strength": 0.0,
            "swing_strength": 0.0,
            "confirmation": "NO DIRECTION",
            "participation_strength": 0.0,
            "structural_strength": 0.0,
            "intraday_type": "NO CLEAR EDGE",
            "swing_type": "NO CLEAR EDGE",
        }

    rel = _num(row.get("relative_score"))
    slope = _num(trend.get("rank_slope"))
    accel = _num(trend.get("acceleration"))
    persistence = _num(trend.get("persistence"))
    profile = trend.get("structural_profile") or {}

    rel_strength = max(0.0, min(1.0, abs(rel - 50.0) / 50.0))
    slope_strength = max(0.0, min(1.0, abs(slope) / 8.0)) if math.isfinite(slope) else 0.0
    accel_strength = max(0.0, min(1.0, abs(accel) / 8.0)) if math.isfinite(accel) else 0.0
    persist_strength = max(0.0, min(1.0, persistence / 100.0)) if math.isfinite(persistence) else 0.0

    def avg(keys):
        vals = [profile.get(k) for k in keys if math.isfinite(_num(profile.get(k)))]
        return float(np.mean(vals) / 100.0) if vals else 0.0

    participation = avg(["price_5_ratio", "breadth_5_ratio", "volume_5_ratio", "oi_5_ratio"])
    structural = avg(["price_10_ratio", "breadth_10_ratio", "volume_10_ratio", "oi_10_ratio"])
    recent = participation

    # Discovery strength is deliberately graded. It is not a probability.
    intraday_strength = 100.0 * (
        0.30 * rel_strength + 0.25 * slope_strength +
        0.20 * accel_strength + 0.15 * recent + 0.10 * persist_strength
    )
    swing_strength = 100.0 * (
        0.30 * rel_strength + 0.25 * slope_strength +
        0.20 * persist_strength + 0.15 * structural + 0.10 * participation
    )

    def level(x: float) -> str:
        if x >= 70: return "HIGH OPPORTUNITY"
        if x >= 52: return "DEVELOPING OPPORTUNITY"
        if x >= 35: return "EARLY OPPORTUNITY"
        return "LOW OPPORTUNITY"

    # Absolute direction agreement is used to describe the *type* of setup.
    # It does not veto an opportunity.
    def ratio_value(key: str, default=float("nan")):
        return _num(profile.get(key, default))

    recent_abs = [
        ratio_value("price_5_ratio"), ratio_value("breadth_5_ratio"),
        ratio_value("volume_5_ratio"), ratio_value("oi_5_ratio")
    ]
    structural_abs = [
        ratio_value("price_10_ratio"), ratio_value("breadth_10_ratio"),
        ratio_value("volume_10_ratio"), ratio_value("oi_10_ratio")
    ]
    recent_valid = [x for x in recent_abs if math.isfinite(x)]
    structural_valid = [x for x in structural_abs if math.isfinite(x)]

    # Ratios are directional: for INTO, high means repeated positive sessions;
    # for OUT, high means repeated negative sessions.
    recent_agree = sum(x >= 60 for x in recent_valid)
    recent_conflict = sum(x <= 40 for x in recent_valid)
    structural_agree = sum(x >= 60 for x in structural_valid)
    structural_conflict = sum(x <= 40 for x in structural_valid)

    # Current absolute direction: 3-session directional deltas are also used.
    price_delta = _num(trend.get("price_delta_3"))
    breadth_delta = _num(trend.get("breadth_delta_3"))
    volume_delta = _num(trend.get("volume_delta_3"))
    oi_delta = _num(trend.get("oi_delta_3"))

    def sign_score(values):
        vals = [x for x in values if math.isfinite(x)]
        if not vals:
            return 0
        return sum(1 if x > 0 else -1 if x < 0 else 0 for x in vals)

    # For OUT, invert the absolute deltas so positive means confirmation of OUT.
    delta_values = [price_delta, breadth_delta, volume_delta, oi_delta]
    if direction == "OUT":
        delta_values = [-x if math.isfinite(x) else x for x in delta_values]
    recent_delta_score = sign_score(delta_values)

    if direction == "INTO":
        if recent_agree >= 3 and recent_conflict <= 1:
            intraday_type = "MOMENTUM"
        elif recent_delta_score >= 2 and rel < 50:
            intraday_type = "RECOVERY / REVERSAL WATCH"
        elif recent_agree <= 1 and recent_conflict >= 3:
            intraday_type = "RELATIVE LEADER ONLY"
        elif recent_agree >= 2:
            intraday_type = "EARLY ROTATION"
        else:
            intraday_type = "CONFLICTED ROTATION"

        if structural_agree >= 3 and structural_conflict <= 1:
            swing_type = "STRUCTURAL LEADERSHIP"
        else:
            structural_delta = sum(
                1 if x >= 60 else -1 if x <= 40 else 0
                for x in structural_valid
            )
            if structural_delta >= 2 and rel < 50:
                swing_type = "STRUCTURAL RECOVERY"
            elif structural_delta <= -2:
                swing_type = "RELATIVE LEADER / PULLBACK"
            else:
                swing_type = "DEVELOPING LEADERSHIP"
    else:
        if recent_agree >= 3 and recent_conflict <= 1:
            intraday_type = "BREAKDOWN / WEAKNESS"
        elif recent_delta_score >= 2 and rel > 50:
            intraday_type = "WEAKENER / REVERSAL WATCH"
        elif recent_agree <= 1 and recent_conflict >= 3:
            intraday_type = "RELATIVE WEAKENER ONLY"
        elif recent_agree >= 2:
            intraday_type = "EARLY DETERIORATION"
        else:
            intraday_type = "CONFLICTED ROTATION"

        if structural_agree >= 3 and structural_conflict <= 1:
            swing_type = "STRUCTURAL DETERIORATION"
        elif structural_valid:
            structural_delta = sum(
                1 if x >= 60 else -1 if x <= 40 else 0
                for x in structural_valid
            )
            if structural_delta >= 2 and rel > 50:
                swing_type = "STRUCTURAL RECOVERY"
            elif structural_delta <= -2:
                swing_type = "STRUCTURAL WEAKNESS"
            else:
                swing_type = "DEVELOPING DETERIORATION"
        else:
            swing_type = "DEVELOPING DETERIORATION"

    agreement = int(row.get("evidence_agreement") or 0)
    conflicts = int(row.get("evidence_conflicts") or 0)
    if conflicts >= 3:
        confirmation = "CONFLICTED"
    elif agreement >= 4 and conflicts <= 1:
        confirmation = "STRONG"
    elif agreement >= 2 and conflicts <= 2:
        confirmation = "MODERATE"
    else:
        confirmation = "LIMITED"

    return {
        "intraday_strength": round(intraday_strength, 1),
        "swing_strength": round(swing_strength, 1),
        "intraday_level": level(intraday_strength),
        "swing_level": level(swing_strength),
        "confirmation": confirmation,
        "participation_strength": round(participation * 100.0, 1),
        "structural_strength": round(structural * 100.0, 1),
        "intraday_type": intraday_type,
        "swing_type": swing_type,
    }

def _trend_metrics(daily: pd.DataFrame, sector: str) -> dict[str, Any]:
    h = _sector_history(daily, sector)
    if h.empty:
        return {}
    slope, acceleration, trajectory = _rank_trajectory(h)
    current = h.iloc[-1]
    n = len(h)
    rel = pd.to_numeric(h["relative_score"], errors="coerce").dropna()
    current_rel = float(rel.iloc[-1]) if not rel.empty else 50.0
    recent = rel.tail(min(5, len(rel)))
    if len(recent) >= 3:
        persistence = float((np.sign(recent - 50) == np.sign(current_rel - 50)).mean() * 100.0)
    else:
        persistence = float((np.sign(recent - 50) == np.sign(current_rel - 50)).mean() * 100.0) if len(recent) else 0.0
    return {
        "rank_slope": slope,
        "acceleration": acceleration,
        "trajectory": trajectory,
        "current_relative": current_rel,
        "rank_change_3": trajectory[-1] - trajectory[-min(3, len(trajectory))] if len(trajectory) >= 2 else float("nan"),
        "rank_change_5": trajectory[-1] - trajectory[-min(5, len(trajectory))] if len(trajectory) >= 2 else float("nan"),
        "rank_change_10": trajectory[-1] - trajectory[0] if len(trajectory) >= 2 else float("nan"),
        "price_delta_3": _delta(h, "price_chg", FAST_SESSIONS),
        "breadth_delta_3": _delta(h, "breadth", FAST_SESSIONS),
        "oi_delta_3": _delta(h, "oi_chg", FAST_SESSIONS),
        "volume_delta_3": _delta(h, "volume_chg", FAST_SESSIONS),
        "ce_oi_delta_3": _delta(h, "ce_oi_chg", FAST_SESSIONS),
        "pe_oi_delta_3": _delta(h, "pe_oi_chg", FAST_SESSIONS),
        "pe_ce_oi_delta_3": _delta(h, "pe_ce_oi_chg", FAST_SESSIONS),
        "ce_oi_delta_10": _delta(h, "ce_oi_chg", STRUCTURAL_SESSIONS),
        "pe_oi_delta_10": _delta(h, "pe_oi_chg", STRUCTURAL_SESSIONS),
        "pe_ce_oi_delta_10": _delta(h, "pe_ce_oi_chg", STRUCTURAL_SESSIONS),
        "persistence": persistence,
        "structural_profile": _structural_profile(h, "INTO" if current_rel > 50 else "OUT" if current_rel < 50 else "NEUTRAL"),
        "sessions_available": n,
    }

def _support(value: float, direction: str, minimum: float = 0.0) -> bool:
    if not math.isfinite(value):
        return False
    return value > minimum if direction == "INTO" else value < -minimum


def _conflict(value: float, direction: str, minimum: float = 0.0) -> bool:
    if not math.isfinite(value):
        return False
    return value < -minimum if direction == "INTO" else value > minimum


def _evidence(row: dict[str, Any], trend: dict[str, Any], direction: str) -> tuple[list[str], int, int, dict[str, str]]:
    """Separate relative evidence from absolute/participation evidence.
    This deliberately prevents a strong relative rank from being labelled a confirmed
    rotation when absolute price/breadth/volume evidence conflicts with it.
    """
    if direction == "NEUTRAL":
        return ["relative leadership and temporal direction are not aligned"], 0, 0, {}

    rel = _num(row.get("relative_score"))
    slope = _num(trend.get("rank_slope"))
    price = _num(row.get("price_chg"))
    breadth = _num(row.get("breadth"))
    volume = _num(row.get("volume_chg"))
    oi = _num(row.get("oi_chg"))
    breadth_delta = _num(trend.get("breadth_delta_3"))
    volume_delta = _num(trend.get("volume_delta_3"))
    oi_delta = _num(trend.get("oi_delta_3"))
    persistence = _num(trend.get("persistence"))

    evidence: list[str] = []
    states: dict[str, str] = {}
    supporting = 0
    conflicts = 0

    if (rel > 50) == (direction == "INTO"):
        evidence.append("relative leadership is aligned")
        supporting += 1
        states["relative"] = "SUPPORTING"
    else:
        conflicts += 1
        states["relative"] = "CONFLICTING"

    if math.isfinite(slope):
        if _support(slope, direction):
            evidence.append("leadership trajectory is moving in the same direction")
            supporting += 1
            states["leadership"] = "SUPPORTING"
        elif _conflict(slope, direction):
            evidence.append("leadership trajectory conflicts with the current direction")
            conflicts += 1
            states["leadership"] = "CONFLICTING"
        else:
            states["leadership"] = "FLAT"

    for key, value, label in (
        ("price", price, "price"),
        ("breadth", breadth, "breadth"),
        ("volume", volume, "volume"),
        ("oi", oi, "OI"),
    ):
        if _support(value, direction):
            evidence.append(f"{label} is directionally supportive")
            supporting += 1
            states[key] = "SUPPORTING"
        elif _conflict(value, direction):
            evidence.append(f"{label} is conflicting with the direction")
            conflicts += 1
            states[key] = "CONFLICTING"
        else:
            states[key] = "NEUTRAL"

    if math.isfinite(persistence) and persistence >= 60:
        evidence.append("directional leadership has persisted across recent sessions")
        states["persistence"] = "SUPPORTING"
    elif math.isfinite(persistence):
        states["persistence"] = "LIMITED"

    return evidence[:7] or ["evidence is mixed; confirmation is limited"], supporting, conflicts, states


def _state(direction: str, relative_score: float, slope: float, acceleration: float, persistence: float,
           sessions: int, supporting: int, conflicts: int) -> str:
    if sessions < 3:
        return "EARLY ROTATION" if direction != "NEUTRAL" else "INSUFFICIENT HISTORY"
    if direction == "NEUTRAL":
        return "CONFLICTING"
    if conflicts >= 3 and supporting <= conflicts:
        return "RELATIVE LEADER ONLY" if direction == "INTO" else "RELATIVE WEAKENER ONLY"
    if direction == "INTO":
        if acceleration < 0 and slope < 0:
            return "EXHAUSTING"
        if supporting >= 5 and conflicts <= 1 and relative_score >= 60 and slope > 1.0 and persistence >= 50:
            return "CONFIRMED"
        if supporting >= 3 and slope > 1.0:
            return "DEVELOPING"
        return "RELATIVE LEADER ONLY"
    if acceleration > 0 and slope > 0:
        return "EXHAUSTING"
    if supporting >= 5 and conflicts <= 1 and relative_score <= 40 and slope < -1.0 and persistence >= 50:
        return "CONFIRMED OUT"
    if supporting >= 3 and slope < -1.0:
        return "DEVELOPING OUT"
    return "RELATIVE WEAKENER ONLY"


def _materiality(state: str, direction: str, relative_score: float, slope: float, supporting: int, conflicts: int, sessions: int) -> tuple[bool, bool]:
    """Evidence gate using peer-relative position and agreement, not raw absolute cutoffs.

    The 80/20 peer split is a ranking convention: it adapts to the number and
    distribution of sectors in the current cross-section. It is not a claim that
    a fixed price/OI percentage is universally material.
    """
    if sessions < 3 or direction == "NEUTRAL":
        return False, False
    strong_relative = relative_score >= 80 if direction == "INTO" else relative_score <= 20
    meaningful_relative = relative_score >= 65 if direction == "INTO" else relative_score <= 35
    moving = (slope > 0) if direction == "INTO" else (slope < 0)
    material = strong_relative and moving and supporting >= 3 and conflicts <= 1
    watch = meaningful_relative and moving and supporting >= 2
    if state in {"RELATIVE LEADER ONLY", "RELATIVE WEAKENER ONLY"}:
        material = False
        watch = True
    return material, watch


def build_sector_intelligence(history: pd.DataFrame) -> dict[str, Any]:
    if history.empty or "sector" not in history.columns:
        return {"generated": True, "focus": [], "watch": [], "ignored": [], "reason": "No usable Sector Summary history."}

    daily = _prepare_daily(history)
    if daily.empty:
        return {"generated": True, "focus": [], "watch": [], "ignored": [], "reason": "No usable daily sector observations."}

    sessions = sorted(daily["_session"].unique())
    latest_session = sessions[-1]
    latest = daily[daily["_session"] == latest_session].copy()
    rows: list[dict[str, Any]] = []

    for _, r in latest.iterrows():
        sector = str(r["sector"]).strip()
        trend = _trend_metrics(daily, sector)
        rel = _num(r.get("relative_score"))
        slope = _num(trend.get("rank_slope"))
        direction = "INTO" if rel > 50 and slope > 1.0 else "OUT" if rel < 50 and slope < -1.0 else "NEUTRAL"
        evidence, supporting, conflicts, evidence_states = _evidence(r.to_dict(), trend, direction)
        state = _state(direction, rel, slope, _num(trend.get("acceleration")), _num(trend.get("persistence")), trend.get("sessions_available", 0), supporting, conflicts)
        material, watch = _materiality(state, direction, rel, slope, supporting, conflicts, trend.get("sessions_available", 0))

        def val(key: str, nd: int = 2):
            x = _num(r.get(key))
            return round(x, nd) if math.isfinite(x) else None

        opportunity = _opportunity_profile(
            {"relative_score": rel, "evidence_agreement": supporting, "evidence_conflicts": conflicts},
            trend,
            direction,
        )
        rows.append({
            "sector": sector,
            "direction": direction,
            "state": state,
            "attention": "FOCUS" if material else "WATCH" if watch else "IGNORE",
            "relative_strength": val("relative_score", 1),
            "rank_slope": val("rank_slope", 2) if "rank_slope" in r else round(slope, 2),
            "rank_trajectory": [round(float(x), 1) for x in trend.get("trajectory", [])],
            "rank_change_3": round(_num(trend.get("rank_change_3")), 1) if math.isfinite(_num(trend.get("rank_change_3"))) else None,
            "rank_change_5": round(_num(trend.get("rank_change_5")), 1) if math.isfinite(_num(trend.get("rank_change_5"))) else None,
            "rank_change_10": round(_num(trend.get("rank_change_10")), 1) if math.isfinite(_num(trend.get("rank_change_10"))) else None,
            "persistence": val("persistence", 1) if "persistence" in r else round(_num(trend.get("persistence")), 1),
            "price": val("price_chg"),
            "breadth": val("breadth", 1),
            "oi": val("oi_chg"),
            "volume": val("volume_chg"),
            "price_delta_3": round(_num(trend.get("price_delta_3")), 2) if math.isfinite(_num(trend.get("price_delta_3"))) else None,
            "breadth_delta_3": round(_num(trend.get("breadth_delta_3")), 1) if math.isfinite(_num(trend.get("breadth_delta_3"))) else None,
            "oi_delta_3": round(_num(trend.get("oi_delta_3")), 2) if math.isfinite(_num(trend.get("oi_delta_3"))) else None,
            "volume_delta_3": round(_num(trend.get("volume_delta_3")), 2) if math.isfinite(_num(trend.get("volume_delta_3"))) else None,
            "ce_oi_change": val("ce_oi_chg"),
            "pe_oi_change": val("pe_oi_chg"),
            "pe_ce_oi_change": val("pe_ce_oi_chg"),
            "ce_oi_delta_3": round(_num(trend.get("ce_oi_delta_3")), 2) if math.isfinite(_num(trend.get("ce_oi_delta_3"))) else None,
            "pe_oi_delta_3": round(_num(trend.get("pe_oi_delta_3")), 2) if math.isfinite(_num(trend.get("pe_oi_delta_3"))) else None,
            "pe_ce_oi_delta_3": round(_num(trend.get("pe_ce_oi_delta_3")), 2) if math.isfinite(_num(trend.get("pe_ce_oi_delta_3"))) else None,
            "ce_oi_delta_10": round(_num(trend.get("ce_oi_delta_10")), 2) if math.isfinite(_num(trend.get("ce_oi_delta_10"))) else None,
            "pe_oi_delta_10": round(_num(trend.get("pe_oi_delta_10")), 2) if math.isfinite(_num(trend.get("pe_oi_delta_10"))) else None,
            "pe_ce_oi_delta_10": round(_num(trend.get("pe_ce_oi_delta_10")), 2) if math.isfinite(_num(trend.get("pe_ce_oi_delta_10"))) else None,
            "evidence_agreement": supporting,
            "evidence_conflicts": conflicts,
            "evidence": evidence,
            "evidence_states": evidence_states,
            "flow_proxy": _flow_direction(_num(r.get("price_chg")), _num(r.get("oi_chg")), _parse_buildup(r.get("buildup"))),
            "intraday_strength": opportunity["intraday_strength"],
            "swing_strength": opportunity["swing_strength"],
            "intraday_opportunity": opportunity["intraday_level"],
            "swing_opportunity": opportunity["swing_level"],
            "intraday_type": opportunity["intraday_type"],
            "swing_type": opportunity["swing_type"],
            "confirmation_quality": opportunity["confirmation"],
            "participation_strength": opportunity["participation_strength"],
            "structural_strength": opportunity["structural_strength"],
            "buildup": _parse_buildup(r.get("buildup")),
            "observed_at": str(r.get("observed_at")),
            "sessions_available": int(trend.get("sessions_available", 0)),
        })

    # Stronger decision ordering: confirmation quality first, then relative distance and slope.
    rows.sort(key=lambda x: (
        x["attention"] == "FOCUS",
        max(x.get("intraday_strength", 0.0), x.get("swing_strength", 0.0)),
        x["evidence_agreement"] - x["evidence_conflicts"],
        abs(x["relative_strength"] - 50),
        abs(x["rank_slope"]),
    ), reverse=True)
    focus = [x for x in rows if x["attention"] == "FOCUS"][:8]
    watch = [x for x in rows if x["attention"] == "WATCH"][:8]
    ignored = [x for x in rows if x["attention"] == "IGNORE"]

    return {
        "generated": True,
        "sessions": len(sessions),
        "session_dates": [str(pd.Timestamp(x).date()) for x in sessions[-STRUCTURAL_SESSIONS:]],
        "latest_observation": str(pd.to_datetime(history["observed_at"], errors="coerce").max()),
        "focus": focus,
        "watch": watch,
        "ignored_count": len(ignored),
        "all_count": len(rows),
        "method": "relative leadership + absolute price/breadth/volume/OI confirmation + temporal rank trajectory",
        "materiality": "provisional relative + confirmation gate; thresholds require historical calibration",
    }
