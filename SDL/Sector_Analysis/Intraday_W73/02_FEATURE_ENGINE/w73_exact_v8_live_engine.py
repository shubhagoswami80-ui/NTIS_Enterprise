"""
NTIS SDL Intraday W73 — Exact V8 Live Derivation v1

Purpose
-------
Derive the frozen V8 feature vector from W73 point-in-time observations
without inventing reconstructed semantics.

Authoritative semantic sources:
- maturity_conditional_pattern_discovery_v8.py
- data_strength_combination_study.py
- smart_replay_strategy_study.py
- existing W73 v8_feature_engine.py for trajectory/matching contract

This module is fail-closed:
- missing evidence remains missing;
- no future observation is admitted;
- V8 state semantics mirror the authoritative source code;
- the historical target reached_0_5x is NEVER used as a live input;
- a vector is only READY when every required exact-V8 field is present.

The raw Daywise workbook is not assumed to be a complete futures source.
If the authoritative canonical mapping requires a FUTURES-family field that is
not present in the live observations, that field remains missing and the exact
V8 vector remains NOT_READY.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, time
from typing import Any, Mapping, Sequence
import math
import re

import pandas as pd

V8_COLUMNS = (
    "orb_minutes",
    "maturity",
    "orb_dir",
    "price_dir",
    "fut_dir",
    "option_dir",
    "fut_state",
    "volume_state",
    "ce_state",
    "pe_state",
    "pec_state",
    "fut_oi_state",
    "ce_pct_state",
    "pe_pct_state",
    "pec_pct_state",
    "fut_pct_state",
    "price_state",
    "orb_agree",
    "evidence_agreement",
    "persistent",
    "strength_bucket",
    "core_count_band",
    "magnitude_count_band",
    "orb_fut_agree",
    "orb_price_agree",
)

MATURITY_CUTS = {
    "09:30": time(9, 30),
    "09:45": time(9, 45),
    "10:00": time(10, 0),
    "10:15": time(10, 15),
}

W73_A_CONDITION = {
    "orb_agree": "NO",
    "magnitude_count_band": 0,
    "px_all_negative_pre_maturity": True,
}

W73_B_CONDITION = {
    "orb_price_agree": "NO",
    "magnitude_count_band": 0,
    "px_all_negative_pre_maturity": True,
}


@dataclass(frozen=True)
class ExactV8Result:
    status: str
    symbol: str
    trading_date: str
    observation_timestamp: str
    orb_minutes: int
    maturity: str
    feature_vector: dict[str, Any]
    missing_fields: tuple[str, ...]
    trajectory: dict[str, Any]
    variants: dict[str, bool]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def _num(v: Any) -> float | None:
    if _missing(v):
        return None
    try:
        x = float(str(v).replace(",", "").replace("−", "-").replace("%", ""))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _timestamp(row: Mapping[str, Any]) -> datetime | None:
    raw = row.get("_observation_timestamp", row.get("timestamp"))
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def _direction(v: Any) -> str:
    x = _num(v)
    if x is None or x == 0:
        return "FLAT"
    return "UP" if x > 0 else "DOWN"


def _norm_dir(v: Any) -> str:
    s = str(v).upper().strip()
    if "UP" in s:
        return "UP"
    if "DOWN" in s:
        return "DOWN"
    return "OTHER"


def _truth(v: Any) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def _parse_state(v: Any) -> str:
    m = re.search(r"\b(LB|SB|SC)\b", str(v).upper())
    return m.group(1) if m else ""


def _sign_state(v: Any) -> str | None:
    x = _num(v)
    if x is None:
        return None
    if x > 0:
        return "POS"
    if x < 0:
        return "NEG"
    return "ZERO"


def _family(row: Mapping[str, Any]) -> str:
    return str(row.get("family", row.get("source_family", "OPTIONS"))).upper()


def canonicalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the authoritative data_strength field-role mapping.

    The mapping is intentionally conservative. In particular, FUTURES OI
    fields are only taken from FUTURES-family observations; a generic Daywise
    OI field is not silently relabelled as futures OI.
    """
    fam = _family(row)

    out = {
        "symbol": str(row.get("Symbol", row.get("symbol", ""))).strip().upper(),
        "timestamp": _timestamp(row),
        "family": fam,
        "price_chg": _num(row.get("Price Chg")),
        "price_chg_pct": _num(row.get("Price Chg %")),
        "volume_pct": _num(row.get("Volume Chg (%)")),
        "ce_num": _num(row.get("Tot CE OI Chg")),
        "pe_num": _num(row.get("Tot PE OI Chg")),
        "pec_num": _num(row.get("Tot PE-CE OI Chg")),
        "ce_pct": _num(row.get("Tot CE OI Chg %")),
        "pe_pct": _num(row.get("Tot PE OI Chg %")),
        "pec_pct": _num(row.get("Tot PE-CE OI Chg %")),
        "fut_num": _num(row.get("OI Chg")) if fam == "FUTURES" else None,
        "fut_pct": _num(row.get("OI Chg %")) if fam == "FUTURES" else None,
        "fut_state": _parse_state(row.get("Buildup", row.get("Fut Buildup"))),
        "iv_chg": _num(row.get("IV Chg")),
        "iv_chg_pct": _num(row.get("IV Chg %")),
        "pcr_chg": _num(row.get("PCR Chg")),
        "pcr_chg_pct": _num(row.get("PCR Chg %")),
        "straddle_pct": _num(row.get("ATM Straddle %")),
        "straddle": _num(row.get("ATM Straddle Price")),
        "buildup": row.get("Buildup"),
        "support": row.get("Support"),
        "resistance": row.get("Resistance"),
        "open": _num(row.get("Open")),
        "high": _num(row.get("High")),
        "low": _num(row.get("Low")),
        "close": _num(row.get("Close")),
    }
    return out


def option_direction(row: Mapping[str, Any]) -> str:
    pec = row.get("pec_num")
    if pec is not None and pec != 0:
        return "UP" if pec > 0 else "DOWN"
    return ""


def _fut_direction(row: Mapping[str, Any]) -> str:
    state = row.get("fut_state")
    pdirection = _direction(row.get("price_chg"))
    if state == "LB" and pdirection == "UP":
        return "UP"
    if state in ("SB", "SC") and pdirection == "DOWN":
        return "DOWN"
    return ""


def _agreement(row: Mapping[str, Any]) -> str:
    dirs = [
        x for x in (
            _direction(row.get("price_chg")),
            option_direction(row),
            _fut_direction(row),
        )
        if x in ("UP", "DOWN")
    ]
    if not dirs:
        return "NONE"
    return "AGREE" if len(set(dirs)) == 1 else "MIXED"


def _volume_band(values: Sequence[Mapping[str, Any]]) -> dict[int, str]:
    vals = [abs(x) for r in values if (x := _num(r.get("Volume Chg (%)"))) is not None]
    if not vals:
        return {}
    s = pd.Series(vals)
    qs = s.quantile([.50, .75, .90, .95]).to_dict()
    out: dict[int, str] = {}
    for idx, r in enumerate(values):
        v = _num(r.get("Volume Chg (%)"))
        if v is None:
            out[idx] = ""
        elif abs(v) >= qs[.95]:
            out[idx] = "V95"
        elif abs(v) >= qs[.90]:
            out[idx] = "V90"
        elif abs(v) >= qs[.75]:
            out[idx] = "V75"
        elif abs(v) >= qs[.50]:
            out[idx] = "V50"
        else:
            out[idx] = "V<50"
    return out


def _strength_bucket(row: Mapping[str, Any], volume_band: str, persistent: bool) -> str:
    core = sum(
        row.get(k) is not None
        for k in ("price_chg", "volume_pct", "ce_num", "pe_num", "pec_num", "fut_num", "fut_pct")
    )
    magnitude = sum([
        row.get("ce_num") is not None and abs(row["ce_num"]) > 500,
        row.get("pe_num") is not None and abs(row["pe_num"]) > 500,
        row.get("pec_num") is not None and abs(row["pec_num"]) > 500,
        row.get("fut_num") is not None and abs(row["fut_num"]) > 500,
        row.get("fut_pct") is not None and abs(row["fut_pct"]) > 1,
        volume_band in {"V75", "V90", "V95"},
    ])
    agreement = _agreement(row)
    if core >= 5 and magnitude >= 3 and agreement == "AGREE" and persistent:
        return "VERY_STRONG"
    if core >= 4 and magnitude >= 2 and agreement == "AGREE":
        return "STRONG"
    if core >= 3 and magnitude >= 1:
        return "MODERATE"
    return "WEAK"


def _build_persistent_signature(row: Mapping[str, Any]) -> str:
    return "|".join(str(row.get(k) or "") for k in (
        "price_direction", "option_direction", "fut_direction", "volume_band"
    ))


def _prepare_canonical_history(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    canon = [canonicalize_row(r) for r in rows]
    canon = [r for r in canon if r["symbol"] and r["timestamp"] is not None]
    canon.sort(key=lambda x: (x["symbol"], x["timestamp"], x["family"]))
    volume_bands = _volume_band(canon)
    for i, r in enumerate(canon):
        r["price_direction"] = _direction(r["price_chg"])
        r["option_direction"] = option_direction(r)
        r["fut_direction"] = _fut_direction(r)
        r["direction_agreement"] = _agreement(r)
        r["volume_band"] = volume_bands.get(i, "")
        r["_signature"] = _build_persistent_signature(r)
        r["persistent"] = False
    by_symbol: dict[str, list[int]] = {}
    for i, r in enumerate(canon):
        by_symbol.setdefault(r["symbol"], []).append(i)
    for idxs in by_symbol.values():
        for pos in range(1, len(idxs)):
            cur, prev = canon[idxs[pos]], canon[idxs[pos - 1]]
            if cur["_signature"] and cur["_signature"] == prev["_signature"]:
                delta = (cur["timestamp"] - prev["timestamp"]).total_seconds()
                if 1 <= delta <= 900:
                    cur["persistent"] = True
        for i in idxs:
            canon[i]["strength_bucket"] = _strength_bucket(
                canon[i], canon[i]["volume_band"], canon[i]["persistent"]
            )
            canon[i]["core_evidence_count"] = sum(
                canon[i].get(k) is not None
                for k in ("price_chg", "volume_pct", "ce_num", "pe_num", "pec_num", "fut_num", "fut_pct")
            )
            canon[i]["magnitude_count"] = sum([
                canon[i].get("ce_num") is not None and abs(canon[i]["ce_num"]) > 500,
                canon[i].get("pe_num") is not None and abs(canon[i]["pe_num"]) > 500,
                canon[i].get("pec_num") is not None and abs(canon[i]["pec_num"]) > 500,
                canon[i].get("fut_num") is not None and abs(canon[i]["fut_num"]) > 500,
                canon[i].get("fut_pct") is not None and abs(canon[i]["fut_pct"]) > 1,
                canon[i]["volume_band"] in {"V75", "V90", "V95"},
            ])
    return canon


def build_price_stream(canon: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in canon:
        if not all(r.get(k) is not None for k in ("open", "high", "low", "close")):
            continue
        day = r["timestamp"].date().isoformat()
        groups.setdefault((r["symbol"], day), []).append(dict(r))
    for key in groups:
        groups[key].sort(key=lambda x: x["timestamp"])
    return groups


def orb_anchor(price_rows: Sequence[Mapping[str, Any]], orb_minutes: int) -> dict[str, Any] | None:
    if not price_rows:
        return None
    t0 = price_rows[0]["timestamp"]
    cutoff = t0 + pd.Timedelta(minutes=orb_minutes)
    orb = [r for r in price_rows if r["timestamp"] <= cutoff]
    if len(orb) < 2:
        return None
    hi = max(r["high"] for r in orb)
    lo = min(r["low"] for r in orb)
    if not math.isfinite(hi - lo) or hi <= lo:
        return None
    later = [r for r in price_rows if r["timestamp"] > cutoff]
    if not later:
        return None
    up = next((r for r in later if r["close"] > hi), None)
    dn = next((r for r in later if r["close"] < lo), None)
    # Historical smart replay records the first directional break. For live
    # maturity-state construction, the anchor is the first break that occurs.
    candidates = [x for x in (up, dn) if x is not None]
    if not candidates:
        return None
    hit = min(candidates, key=lambda r: r["timestamp"])
    return {
        "anchor_time": hit["timestamp"],
        "orb_high": hi,
        "orb_low": lo,
        "orb_range": hi - lo,
        "breakout_price": hit["close"],
        "orb_direction": "UP" if hit is up else "DOWN",
    }


def _latest_at(rows: Sequence[Mapping[str, Any]], cutoff: datetime) -> dict[str, Any] | None:
    usable = [r for r in rows if r["timestamp"] <= cutoff]
    return max(usable, key=lambda x: x["timestamp"]) if usable else None


def _latest_evidence_at(canon: Sequence[Mapping[str, Any]], symbol: str, cutoff: datetime) -> dict[str, Any] | None:
    rows = [r for r in canon if r["symbol"] == symbol and r["timestamp"] <= cutoff]
    return max(rows, key=lambda x: x["timestamp"]) if rows else None


def derive_trajectory(price_rows: Sequence[Mapping[str, Any]], maturity_timestamp: datetime) -> dict[str, Any]:
    usable = []
    for r in price_rows:
        ts = r.get("timestamp")
        chg = r.get("price_chg_pct")
        if ts is None or chg is None or ts >= maturity_timestamp:
            continue
        try:
            v = float(chg)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            usable.append(v)
    if not usable:
        return {
            "px_all_negative_pre_maturity": None,
            "px_negative_count_pre_maturity": None,
            "observations_used": 0,
        }
    neg = sum(v < 0 for v in usable)
    return {
        "px_all_negative_pre_maturity": neg == len(usable),
        "px_negative_count_pre_maturity": neg,
        "observations_used": len(usable),
    }


def build_exact_v8(
    rows: Sequence[Mapping[str, Any]],
    *,
    symbol: str,
    trading_date: str,
    maturity: str,
    orb_minutes: int = 15,
) -> ExactV8Result:
    history = _prepare_canonical_history(rows)
    price_by_key = build_price_stream(history)
    price_rows = price_by_key.get((symbol.upper(), trading_date), [])
    if not price_rows:
        return ExactV8Result(
            "NOT_READY", symbol, trading_date, "", orb_minutes, maturity, {},
            tuple(V8_COLUMNS), {}, {"W73-A": False, "W73-B": False},
            {"NO_PRICE_STREAM": True},
            ("NO_PRICE_STREAM",)
        )

    cutoff_time = MATURITY_CUTS[maturity]
    session_date = datetime.fromisoformat(trading_date)
    maturity_ts = session_date.replace(
        hour=cutoff_time.hour, minute=cutoff_time.minute, second=0, microsecond=0
    )

    # For the live maturity snapshot, ORB direction is derived from information
    # available up to the maturity cutoff. A future breakout is never used to
    # label a maturity snapshot.
    t0 = price_rows[0]["timestamp"]
    orb_cutoff = t0 + pd.Timedelta(minutes=orb_minutes)
    orb_rows = [r for r in price_rows if r["timestamp"] <= orb_cutoff and r["timestamp"] <= maturity_ts]
    if len(orb_rows) < 2:
        return ExactV8Result(
            "NOT_READY", symbol, trading_date, maturity_ts.isoformat(),
            orb_minutes, maturity, {}, tuple(V8_COLUMNS), {},
            {"ORB_NOT_ESTABLISHED": True}
        )

    orb_high = max(r["high"] for r in orb_rows if r.get("high") is not None)
    orb_low = min(r["low"] for r in orb_rows if r.get("low") is not None)
    if not math.isfinite(orb_high - orb_low) or orb_high <= orb_low:
        return ExactV8Result(
            "NOT_READY", symbol, trading_date, maturity_ts.isoformat(),
            orb_minutes, maturity, {}, tuple(V8_COLUMNS), {},
            {"ORB_INVALID": True}
        )

    # The authoritative V8 source expects the event's orb_direction. At a live
    # maturity checkpoint, a direction is only known if the breakout occurred
    # before/equal to the maturity cutoff.
    later = [r for r in price_rows if r["timestamp"] > orb_cutoff and r["timestamp"] <= maturity_ts]
    up = next((r for r in later if r["close"] > orb_high), None)
    dn = next((r for r in later if r["close"] < orb_low), None)
    candidates = [x for x in (up, dn) if x is not None]
    if not candidates:
        latest_evidence = _latest_evidence_at(history, symbol, maturity_ts)
        evidence_ts = (
            latest_evidence["timestamp"].isoformat()
            if latest_evidence is not None
            else maturity_ts.isoformat()
        )
        return ExactV8Result(
            "NOT_READY", symbol, trading_date, evidence_ts,
            orb_minutes, maturity, {}, tuple(V8_COLUMNS),
            {"ORB_BREAKOUT_NOT_OBSERVED_BY_MATURITY": True},
            {"W73-A": False, "W73-B": False},
            ("ORB_BREAKOUT_NOT_OBSERVED_BY_MATURITY",)
        )
    anchor = min(candidates, key=lambda r: r["timestamp"])
    orb_dir = "UP" if anchor is up else "DOWN"

    evidence = _latest_evidence_at(history, symbol, maturity_ts)
    if evidence is None:
        return ExactV8Result(
            "NOT_READY", symbol, trading_date, maturity_ts.isoformat(),
            orb_minutes, maturity, {}, tuple(V8_COLUMNS), {},
            {"NO_EVIDENCE_AT_MATURITY": True}
        )

    # Exact V8 build_features semantics, reproduced from the authoritative source.
    raw = {
        "orb_direction": orb_dir,
        "price_direction": evidence.get("price_direction"),
        "fut_direction": evidence.get("fut_direction"),
        "option_direction": evidence.get("option_direction"),
        "fut_state": evidence.get("fut_state"),
        "volume_pct": evidence.get("volume_pct"),
        "ce_num": evidence.get("ce_num"),
        "pe_num": evidence.get("pe_num"),
        "pec_num": evidence.get("pec_num"),
        "fut_num": evidence.get("fut_num"),
        "ce_pct": evidence.get("ce_pct"),
        "pe_pct": evidence.get("pe_pct"),
        "pec_pct": evidence.get("pec_pct"),
        "fut_pct": evidence.get("fut_pct"),
        "price_chg_pct": evidence.get("price_chg_pct"),
        "direction_agreement_with_orb": evidence.get("direction_agreement") == "AGREE",
        "direction_agreement": evidence.get("direction_agreement"),
        "persistent": evidence.get("persistent"),
        "strength_bucket": evidence.get("strength_bucket"),
        "core_evidence_count": evidence.get("core_evidence_count"),
        "magnitude_count": evidence.get("magnitude_count"),
    }

    f: dict[str, Any] = {}
    f["orb_dir"] = _norm_dir(raw["orb_direction"])
    f["price_dir"] = _norm_dir(raw["price_direction"])
    f["fut_dir"] = _norm_dir(raw["fut_direction"])
    f["option_dir"] = _norm_dir(raw["option_direction"])
    f["fut_state"] = str(raw["fut_state"]).upper().strip() if not _missing(raw["fut_state"]) else None
    f["volume_state"] = _sign_state(raw["volume_pct"])
    f["ce_state"] = _sign_state(raw["ce_num"])
    f["pe_state"] = _sign_state(raw["pe_num"])
    f["pec_state"] = _sign_state(raw["pec_num"])
    f["fut_oi_state"] = _sign_state(raw["fut_num"])
    f["ce_pct_state"] = _sign_state(raw["ce_pct"])
    f["pe_pct_state"] = _sign_state(raw["pe_pct"])
    f["pec_pct_state"] = _sign_state(raw["pec_pct"])
    f["fut_pct_state"] = _sign_state(raw["fut_pct"])
    f["price_state"] = _sign_state(raw["price_chg_pct"])
    f["orb_agree"] = "YES" if bool(raw["direction_agreement_with_orb"]) else "NO"
    f["evidence_agreement"] = str(raw["direction_agreement"]).upper().strip() if not _missing(raw["direction_agreement"]) else None
    f["persistent"] = "YES" if _truth(raw["persistent"]) else "NO"
    f["strength_bucket"] = str(raw["strength_bucket"]).upper().strip() if not _missing(raw["strength_bucket"]) else None
    core = _num(raw["core_evidence_count"])
    mag = _num(raw["magnitude_count"])
    # Exact source uses pd.cut(..., [-1,0,1,2,99], labels ['0','1','2','3+']).
    f["core_count_band"] = None if core is None else ("0" if core <= 0 else "1" if core <= 1 else "2" if core <= 2 else "3+")
    f["magnitude_count_band"] = None if mag is None else ("0" if mag <= 0 else "1" if mag <= 1 else "2" if mag <= 2 else "3+")
    f["orb_fut_agree"] = "YES" if f["orb_dir"] in {"UP","DOWN"} and f["orb_dir"] == f["fut_dir"] else "NO"
    f["orb_price_agree"] = "YES" if f["orb_dir"] in {"UP","DOWN"} and f["orb_dir"] == f["price_dir"] else "NO"

    feature_vector = {
        "orb_minutes": orb_minutes,
        "maturity": maturity,
        **f,
    }

    missing = tuple(c for c in V8_COLUMNS if _missing(feature_vector.get(c)))
    traj = derive_trajectory(price_rows, maturity_ts)
    variants = {
        "W73-A": (
            not missing and
            feature_vector["orb_agree"] == "NO" and
            feature_vector["magnitude_count_band"] == "0" and
            traj["px_all_negative_pre_maturity"] is True
        ),
        "W73-B": (
            not missing and
            feature_vector["orb_price_agree"] == "NO" and
            feature_vector["magnitude_count_band"] == "0" and
            traj["px_all_negative_pre_maturity"] is True
        ),
    }

    warnings = []
    if missing:
        warnings.append("EXACT_V8_INPUTS_INCOMPLETE")
    if traj["px_all_negative_pre_maturity"] is None:
        warnings.append("TRAJECTORY_INCOMPLETE")
    if missing or traj["px_all_negative_pre_maturity"] is None:
        status = "NOT_READY"
    else:
        status = "READY"

    obs_ts = evidence["timestamp"].isoformat()
    return ExactV8Result(
        status, symbol, trading_date, obs_ts, orb_minutes, maturity,
        feature_vector, missing, traj, variants, tuple(warnings)
    )
