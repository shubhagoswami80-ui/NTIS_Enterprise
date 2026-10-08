from __future__ import annotations

import sys
import time
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT / "02_FEATURE_ENGINE", ROOT / "03_LIVE_ADAPTER", ROOT / "06_ALERTS"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from w73_live_ingestor import ingest, source_root, discover_files
from w73_point_in_time_service import load_rows, latest_as_of
from w73_universe_engine import load_config, evaluate
from w73_live_decision_service import evaluate_latest_maturity, evaluate_symbol, decision_summary


st.set_page_config(
    page_title="NTIS W73 — Intraday Trader Board",
    page_icon="W73",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CACHE_ROOT = ROOT / "07_OUTPUT" / "live_cache"
UNIVERSE_CONFIG = ROOT / "07_OUTPUT" / "universe_config.json"
SOURCE_TRUTH_SYMBOLS = (
    "BANDHANBNK",
    "MOTILALOFS",
    "POLICYBZR",
    "RADICO",
    "SAIL",
)


def _source_truth_symbols():
    """Return the controlled Source-of-Truth population.

    Population membership is separate from W73-A/B qualification.
    A member may remain NOT_READY; no gate or feature semantics change.
    """
    try:
        cfg = load_config(UNIVERSE_CONFIG)
        configured = cfg.get("source_truth_symbols")
        if isinstance(configured, (list, tuple)) and configured:
            values = tuple(str(x).strip().upper() for x in configured if str(x).strip())
            if values:
                return values
    except Exception:
        pass
    return SOURCE_TRUTH_SYMBOLS


# ---------------------------------------------------------------------
# Trader-board UI
# ---------------------------------------------------------------------
st.markdown(
    """
<style>
.stApp {background:#071523;color:#e8f0f7;}
[data-testid="stHeader"] {background:rgba(7,21,35,.96);}
section[data-testid="stSidebar"] {
    background:#eef3f7 !important;
    border-right:1px solid #b8c7d3;
    width:300px !important;
    min-width:300px !important;
}
section[data-testid="stSidebar"] > div:first-child {padding-top:.45rem;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.30rem;}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {color:#17212b !important;}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {font-size:.88rem !important;font-weight:800 !important;}
[data-testid="stSidebar"] label {font-size:.80rem !important;font-weight:650 !important;}
[data-testid="stSidebar"] input {font-size:.80rem !important;color:#17212b !important;background:#ffffff !important;border:1px solid #9fb0bd !important;}
[data-testid="stSidebar"] [data-baseweb="select"] > div {background:#ffffff !important;color:#17212b !important;border-color:#9fb0bd !important;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#17212b !important;}
[data-testid="stSidebar"] [role="radiogroup"] label,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label {font-size:.77rem !important;color:#17212b !important;}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radio"] {background:#ffffff !important;}
[data-testid="stSidebar"] button {font-size:.78rem !important;color:#17212b !important;background:#ffffff !important;border:1px solid #8fa3b2 !important;}
[data-testid="stSidebar"] .stButton button {padding:.30rem .45rem !important;font-weight:750 !important;}
[data-testid="stSidebar"] [data-testid="stSlider"] * {color:#17212b !important;}
[data-testid="stSidebar"] .stCaption {font-size:.68rem !important;color:#435563 !important;}
[data-testid="stSidebar"] hr {border-color:#c4d0d9 !important;}

.block-container {padding:.42rem .55rem .45rem .55rem;max-width:100%;}
h1 {font-size:1.38rem !important;margin:0 !important;color:#f2f7fb !important;}
h2 {font-size:.92rem !important;margin:.22rem 0 .14rem 0 !important;color:#dce9f3 !important;}
h3 {font-size:.80rem !important;color:#c9d8e4 !important;}
div[data-testid="stMetric"] {padding:.12rem .25rem;border:1px solid #1b3b55;border-radius:5px;background:#0a1d2d;}
div[data-testid="stMetricLabel"] {font-size:.66rem !important;color:#9eb3c2 !important;}
div[data-testid="stMetricValue"] {font-size:.98rem !important;color:#edf6fb !important;}
div[data-testid="stDataFrame"] {border:1px solid #1b3b55;border-radius:5px;}
.small-note {font-size:.60rem;opacity:.72;}
.w73-session-strip {margin:.16rem 0 .28rem 0;padding:.22rem .42rem;border:1px solid #183b55;border-radius:5px;background:#0a1d2d;color:#9fb5c5;font-size:.61rem;}
.w73-live-dot {color:#20d88b;}
.w73-decision-card {border:1px solid #1b4c68;border-radius:7px;padding:8px;background:#0a1d2d;margin-bottom:7px;}
.w73-decision-symbol {font-size:1.18rem;font-weight:900;color:#5ec8ff;}
.w73-decision-state {font-size:.78rem;font-weight:900;margin-top:2px;}
.w73-critical {font-size:.67rem;line-height:1.32;margin-top:5px;}
.w73-critical b {color:#dce9f3;}
.w73-gate {border:1px solid rgba(100,160,200,.16);border-radius:5px;padding:5px 6px;margin-bottom:4px;background:rgba(8,27,44,.72);}
.w73-gate-ready {color:#20d88b;font-size:.66rem;}
.w73-gate-fail {color:#ff5b68;font-size:.66rem;}
.w73-gate-wait {color:#f0b429;font-size:.66rem;}
.w73-gate strong {float:right;font-size:.60rem;}
.w73-gate-detail {font-size:.57rem;opacity:.72;margin-top:2px;line-height:1.15;}
.w73-summary-label {display:flex;justify-content:space-between;font-size:.62rem;margin-top:3px;}
.w73-summary-track {height:4px;border-radius:4px;background:#172b3b;overflow:hidden;margin:2px 0 4px;}
.w73-bar-qualified {height:100%;background:#20d88b;}
.w73-bar-wait {height:100%;background:#f0b429;}
.w73-bar-notready {height:100%;background:#ff5b68;}
.w73-mini-panel {border:1px solid #183b55;border-radius:6px;padding:7px;background:#0a1d2d;font-size:.61rem;line-height:1.28;}
.w73-first-alert {font-weight:800;color:#f0d36b;}
.w73-validation {font-size:.62rem;padding:5px 7px;border-radius:5px;background:#0a1d2d;border:1px solid #183b55;}
.w73-acceptance-head {font-size:.78rem;font-weight:900;color:#f0d36b;margin:.18rem 0 .24rem;}
@media (max-width: 900px) {
  .block-container {padding:.35rem .25rem .45rem .25rem;}
  h1 {font-size:1.18rem !important;}
  div[data-testid="stMetricValue"] {font-size:.82rem !important;}
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _date_from_cache(path: Path):
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


def _has_authoritative_source(trading_date: str, month: str) -> bool:
    try:
        return bool(discover_files(trading_date, month))
    except Exception:
        return False

def _find_latest_prior_cache(requested_date: str, month: str = "September26"):
    try:
        requested = date.fromisoformat(requested_date)
    except ValueError:
        return None, None, []

    if not CACHE_ROOT.exists():
        return None, None, []

    candidates = []
    for path in CACHE_ROOT.glob("*.jsonl"):
        d = _date_from_cache(path)
        if d is not None and d < requested:
            candidates.append((d, path))

    for d, path in sorted(candidates, reverse=True):
        if not _has_authoritative_source(d.isoformat(), month):
            continue
        try:
            rows = load_rows(path)
        except Exception:
            rows = []
        if rows:
            return d.isoformat(), path, rows
    return None, None, []


def _observation_times(rows):
    return sorted(
        {str(r.get("_observation_timestamp")) for r in rows if r.get("_observation_timestamp")}
    )


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _age_seconds(value):
    ts = _parse_dt(value)
    if ts is None:
        return None
    return max(0, int((datetime.now() - ts).total_seconds()))


def _age_label(value):
    sec = _age_seconds(value)
    if sec is None:
        return "—"
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60:02d}s"
    return f"{sec // 3600}h {(sec % 3600) // 60:02d}m"


def _duration_label(start_value, end_value):
    start = _parse_dt(start_value)
    end = _parse_dt(end_value)
    if start is None or end is None:
        return "—"
    sec = max(0, int((end - start).total_seconds()))
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60:02d}s"
    return f"{sec // 3600}h {(sec % 3600) // 60:02d}m"


def _num(value):
    try:
        return float(value)
    except Exception:
        return None


def _evidence_metrics(rows):
    if not rows:
        return dict(symbols=0, price=0, oi=0, volume=0, iv=0, pcr=0,
                    buildup=0, straddle=0, complete_core=0, core_pct=0.0)

    def present(key):
        return sum(1 for r in rows if r.get(key) not in (None, "", "NA", "N/A"))

    core_keys = [
        "Close", "Price Chg %", "OI Chg %", "Volume",
        "ATM Straddle Price", "IV", "PCR Chg", "Buildup",
    ]
    complete = sum(
        1 for r in rows
        if all(r.get(k) not in (None, "", "NA", "N/A") for k in core_keys)
    )
    symbols = len({str(r.get("Symbol", "")).upper() for r in rows if r.get("Symbol")})

    return dict(
        symbols=symbols,
        price=present("Price Chg %"),
        oi=present("OI Chg %"),
        volume=present("Volume Chg (%)"),
        iv=present("IV"),
        pcr=present("PCR Chg"),
        buildup=present("Buildup"),
        straddle=present("ATM Straddle Price"),
        complete_core=complete,
        core_pct=round(complete / symbols * 100, 1) if symbols else 0.0,
    )


def _build_board(rows):
    """Legacy universe/evidence board retained for supporting panels only."""
    if not rows:
        return pd.DataFrame(), []

    latest = latest_as_of(rows)
    if not latest:
        return pd.DataFrame(), []

    timestamps = [r.get("_observation_timestamp") for r in latest if r.get("_observation_timestamp")]
    asof = max(timestamps) if timestamps else "N/A"

    cfg = load_config(UNIVERSE_CONFIG)
    decisions = evaluate(latest, asof, cfg)
    dm = {str(d.symbol).upper(): d for d in decisions}

    board = []
    for row in latest:
        symbol = str(row.get("Symbol", "")).upper()
        decision = dm.get(symbol)
        if decision and decision.eligible:
            item = dict(row)
            item["Priority"] = decision.priority_score
            item["Eligibility"] = "QUALIFIED"
            board.append(item)

    df = pd.DataFrame(board)
    if not df.empty:
        df = _add_interpretation(df)
        df = df.sort_values(["Strength", "Priority"], ascending=False)
    return df, latest


def _build_research_layer_board(live_decisions, rows):
    """Build the trader board from authoritative Exact V8 decisions.

    W73-A/B remain frozen. W73-NL is a display/research layer only and uses
    the previously tested T3/T2 trajectory variants without modifying the
    Exact V8 engine or LiveDecision service.
    """
    if not live_decisions:
        return pd.DataFrame()

    latest = latest_as_of(rows) if rows else []
    raw_map = {str(r.get("Symbol", "")).upper(): r for r in latest}
    board = []

    for d in live_decisions:
        symbol = str(getattr(d, "symbol", "")).upper().strip()
        if not symbol:
            continue
        raw = dict(raw_map.get(symbol, {}))
        status = str(getattr(d, "status", "NOT_READY") or "NOT_READY").upper()
        features = getattr(d, "feature_vector", {}) or {}
        variant_value = str(getattr(d, "variant", "") or "").upper()
        trajectory = getattr(d, "trajectory", {}) or {}
        a = variant_value == "W73-A"
        b = variant_value == "W73-B"
        neg = trajectory.get("px_negative_count_pre_maturity")
        try:
            neg_num = int(neg) if neg is not None else None
        except (TypeError, ValueError):
            neg_num = None

        nl_t3_a = status == "READY" and not (a or b) and features.get("orb_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg_num is not None and neg_num <= 3
        nl_t3_b = status == "READY" and not (a or b) and features.get("orb_price_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg_num is not None and neg_num <= 3
        nl_t2_a = status == "READY" and not (a or b) and features.get("orb_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg_num is not None and neg_num <= 2
        nl_t2_b = status == "READY" and not (a or b) and features.get("orb_price_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg_num is not None and neg_num <= 2

        if status != "READY":
            layer = "NOT_READY"
            decision_label = "NOT_READY"
        elif a or b:
            layer = "W73-A/B"
            decision_label = "QUALIFIED"
        elif nl_t3_a or nl_t3_b or nl_t2_a or nl_t2_b:
            layer = "W73-NL"
            decision_label = "NEXT-LAYER RESEARCH"
        else:
            layer = "READY-NONMATCH"
            decision_label = "READY / OTHER"

        raw.update({
            "Symbol": symbol,
            "Layer": layer,
            "Decision": decision_label,
            "Setup State": "READY" if status == "READY" else "WAITING FOR EXACT V8",
            "Strategy Status": status,
            "W73 Maturity": getattr(d, "maturity", "") or "—",
            "W73 Variant": ("W73-A" if a else "W73-B" if b else "—"),
            "Action": getattr(d, "action", "NOT_READY") or "NOT_READY",
            "Strategy Observation Time": getattr(d, "observation_timestamp", "") or "—",
            "Source Timestamp": getattr(d, "source_timestamp", "") or "—",
            "Missing Fields": ", ".join(str(x) for x in (getattr(d, "missing_fields", ()) or ())) or "—",
            "Warnings": ", ".join(str(x) for x in (getattr(d, "warnings", ()) or ())) or "—",
            "Trajectory": trajectory,
            "NL-T3-A": nl_t3_a,
            "NL-T3-B": nl_t3_b,
            "NL-T2-A": nl_t2_a,
            "NL-T2-B": nl_t2_b,
            "NL Negative Count": neg_num if neg_num is not None else "—",
            "W73-A Match": a,
            "W73-B Match": b,
            "Reason": "W73-NL research match" if layer == "W73-NL" else ("Frozen W73-A/B match" if layer == "W73-A/B" else "Exact V8 state"),
        })
        board.append(raw)

    df = pd.DataFrame(board)
    if df.empty:
        return df
    if "Strength" not in df.columns:
        df = _add_interpretation(df)
    # Preserve all READY rows; W73 and NL are ranked ahead of READY/OTHER.
    layer_rank = {"W73-A/B": 0, "W73-NL": 1, "READY-NONMATCH": 2, "NOT_READY": 3}
    df["_layer_rank"] = df["Layer"].map(layer_rank).fillna(9)
    df["_strength_num"] = pd.to_numeric(df.get("Strength", 0), errors="coerce").fillna(0)
    df = df.sort_values(["_layer_rank", "_strength_num", "Symbol"], ascending=[True, False, True])
    return df.drop(columns=["_layer_rank", "_strength_num"], errors="ignore")



def _rows_asof(rows, asof):
    """Return only observations at or before the authoritative PIT cutoff."""
    if not rows or not asof:
        return list(rows or [])
    cutoff = _parse_dt(asof)
    if cutoff is None:
        return list(rows or [])
    out = []
    for r in rows:
        ts = _parse_dt(r.get("_observation_timestamp", r.get("timestamp")))
        if ts is not None and ts <= cutoff:
            out.append(r)
    return out


def _first_qualification(rows, asof=None):
    """Return the first exact source timestamp at which each symbol became eligible, PIT-safe."""
    rows = _rows_asof(rows, asof)
    if not rows:
        return {}

    cfg = load_config(UNIVERSE_CONFIG)
    by_ts = {}
    for row in rows:
        ts = row.get("_observation_timestamp")
        if ts:
            by_ts.setdefault(str(ts), []).append(row)

    first = {}
    for ts in sorted(by_ts):
        snapshot = by_ts[ts]
        decisions = evaluate(snapshot, ts, cfg)
        for decision in decisions:
            symbol = str(decision.symbol).upper()
            if decision.eligible and symbol not in first:
                match = next(
                    (r for r in snapshot if str(r.get("Symbol", "")).upper() == symbol),
                    {},
                )
                mini = _add_interpretation(pd.DataFrame([match]))
                if mini.empty:
                    entry_strength = 0
                    entry_bias = "WATCH"
                    entry_evidence = "filter qualified"
                else:
                    entry_strength = int(mini.iloc[0].get("Strength", 0))
                    entry_bias = str(mini.iloc[0].get("Bias", "WATCH"))
                    entry_evidence = str(mini.iloc[0].get("Evidence", "filter qualified"))
                first[symbol] = {
                    "Filter Alert Time": str(ts),
                    "Qualified Since": str(ts),
                    "Entry Strength": entry_strength,
                    "Entry Bias": entry_bias,
                    "Entry Evidence": entry_evidence,
                    "Entry Priority": decision.priority_score,
                }
    return first

def _qualification_events(rows, asof=None):
    """Derive point-in-time universe state transitions from cached intervals, PIT-safe."""
    rows = _rows_asof(rows, asof)
    if not rows:
        return {}
    cfg = load_config(UNIVERSE_CONFIG)
    by_ts = {}
    for row in rows:
        ts = row.get("_observation_timestamp")
        if ts:
            by_ts.setdefault(str(ts), []).append(row)
    states = {}
    events = {}
    for ts in sorted(by_ts):
        decisions = evaluate(by_ts[ts], ts, cfg)
        current = {str(d.symbol).upper(): bool(d.eligible) for d in decisions}
        symbols = set(states) | set(current)
        for symbol in symbols:
            was = states.get(symbol, False)
            now = current.get(symbol, False)
            if now and not was:
                events.setdefault(symbol, []).append({"event": "QUALIFIED" if symbol not in events else "RE-QUALIFIED", "time": ts})
            elif was and not now:
                events.setdefault(symbol, []).append({"event": "INVALIDATED", "time": ts})
        states = current
    return events


def _validated_strategy_gate(row):
    """Apply only the frozen W73 candidate definition when exact fields exist.

    The historical candidate was V8_PLUS_TRAJECTORY with orb_agree=NO,
    magnitude_count_band=0, and px_all_negative_pre_maturity=True.
    The current live cache does not yet carry all exact V8 trajectory fields,
    so the safe result is NOT EVALUABLE rather than an invented BUY/SELL.
    """
    required = ["orb_agree", "magnitude_count_band", "px_all_negative_pre_maturity", "strategy_family"]
    if not all(k in row for k in required):
        return {
            "Decision": "NO TRADE",
            "Strategy Status": "NOT EVALUABLE",
            "Setup State": "WAITING FOR EXACT V8",
            "Reason": "Exact V8 trajectory fields are not present in the live point-in-time observation.",
            "Invalidation": "No directional action until exact V8 strategy evidence is available and passes.",
        }
    match = (
        str(row.get("strategy_family")) == "V8_PLUS_TRAJECTORY"
        and str(row.get("orb_agree")).upper() == "NO"
        and _num(row.get("magnitude_count_band")) == 0
        and bool(row.get("px_all_negative_pre_maturity")) is True
    )
    if match:
        return {
            "Decision": "STRATEGY MATCH — WATCH",
            "Strategy Status": "FROZEN CANDIDATE MATCH",
            "Setup State": "CANDIDATE",
            "Reason": "Frozen V8 trajectory candidate condition matched; this is not a validated directional BUY/SELL rule.",
            "Invalidation": "Candidate condition must remain true at the current source timestamp.",
        }
    return {
        "Decision": "NO TRADE",
        "Strategy Status": "CANDIDATE NOT MATCHED",
        "Setup State": "NOT ACTIVE",
        "Reason": "Frozen V8 trajectory candidate condition is not satisfied.",
        "Invalidation": "No actionable strategy state.",
    }


def _event_summary(symbol, events, data_asof):
    seq = events.get(symbol, [])
    if not seq:
        return "NO EVENT", "—"
    last = seq[-1]
    return str(last.get("event", "EVENT")), str(last.get("time", "—"))


def _add_interpretation(df):
    """
    Trader interpretation layer.

    This is deliberately an EVIDENCE-STRENGTH meter, not a validated
    probability model or frozen trading strategy. It combines the
    currently available raw evidence into a transparent directional
    reading so the dashboard can rank candidates at a glance.
    """
    strengths = []
    biases = []
    reasons = []
    evidence_counts = []

    for _, r in df.iterrows():
        px = _num(r.get("Price Chg %"))
        oi = _num(r.get("OI Chg %"))
        vol = _num(r.get("Volume Chg (%)"))
        iv = _num(r.get("IV Chg %"))
        pcr = _num(r.get("PCR Chg %"))
        buildup = str(r.get("Buildup") or "").lower()

        long_points = 0
        short_points = 0
        reasons_list = []

        # Price direction is the primary directional evidence.
        if px is not None:
            if px > 0:
                long_points += 25
                reasons_list.append("price↑")
            elif px < 0:
                short_points += 25
                reasons_list.append("price↓")

        # OI + price relationship.
        if px is not None and oi is not None:
            if px > 0 and oi > 0:
                long_points += 20
                reasons_list.append("price+OI")
            elif px < 0 and oi > 0:
                short_points += 20
                reasons_list.append("price↓+OI")
            elif px > 0 and oi < 0:
                long_points += 10
                reasons_list.append("short-cover")
            elif px < 0 and oi < 0:
                short_points += 10
                reasons_list.append("long-unwind")

        # Buildup is treated as supporting evidence.
        if "long buildup" in buildup or "short covering" in buildup:
            long_points += 20
            reasons_list.append("bullish buildup")
        elif "short buildup" in buildup or "long unwinding" in buildup:
            short_points += 20
            reasons_list.append("bearish buildup")

        # Volume confirms participation, without deciding direction.
        volume_support = vol is not None and vol > 0
        if volume_support:
            if long_points >= short_points:
                long_points += 10
            else:
                short_points += 10
            reasons_list.append("volume↑")

        # PCR is supporting context only; no standalone direction.
        if pcr is not None and abs(pcr) > 0:
            if long_points > short_points and pcr > 0:
                long_points += 5
                reasons_list.append("PCR support")
            elif short_points > long_points and pcr < 0:
                short_points += 5
                reasons_list.append("PCR support")

        # IV change is a participation/urgency cue, not direction.
        if iv is not None and abs(iv) > 0:
            if max(long_points, short_points) >= 35:
                if long_points >= short_points:
                    long_points += 5
                else:
                    short_points += 5
                reasons_list.append("IV active")

        raw_strength = max(long_points, short_points)
        strength = min(100, int(round(raw_strength)))
        if long_points >= 60 and long_points > short_points:
            bias = "LONG BIAS"
        elif short_points >= 60 and short_points > long_points:
            bias = "SHORT BIAS"
        else:
            bias = "WATCH"

        if not reasons_list:
            reasons_list.append("insufficient directional evidence")

        strengths.append(strength)
        biases.append(bias)
        reasons.append(" • ".join(reasons_list[:5]))
        evidence_counts.append(sum(
            [
                px is not None,
                oi is not None,
                vol is not None,
                buildup not in ("", "none", "nan"),
                pcr is not None,
                iv is not None,
            ]
        ))

    df = df.copy()
    df["Strength"] = strengths
    df["Bias"] = biases
    df["Evidence"] = reasons
    df["Evidence#"] = evidence_counts
    df["Strength Meter"] = [
        ("█" * max(1, s // 10)) + ("░" * (10 - max(1, s // 10)))
        for s in strengths
    ]
    return df


def _direction_counts(df):
    if df.empty or "Price Chg %" not in df.columns:
        return 0, 0, 0
    p = pd.to_numeric(df["Price Chg %"], errors="coerce")
    return int((p > 0).sum()), int((p < 0).sum()), int(p.eq(0).sum())


def _strategy_decision(row, live_decision=None):
    """Render the authoritative LiveDecision without recomputing strategy state."""
    if live_decision is None:
        return {
            "Decision": "NOT_READY",
            "Strategy Status": "NOT_READY",
            "Setup State": "WAITING FOR EXACT V8",
            "Reason": "No authoritative LiveDecision exists for this symbol at the current maturity.",
            "Invalidation": "No strategy action until the live decision service returns a READY evaluation.",
        }

    status = str(getattr(live_decision, "status", "NOT_READY") or "NOT_READY")
    action = str(getattr(live_decision, "action", "NOT_READY") or "NOT_READY")
    variant = getattr(live_decision, "variant", None)
    maturity = str(getattr(live_decision, "maturity", "") or "")
    observation_timestamp = str(getattr(live_decision, "observation_timestamp", "") or "")
    source_timestamp = str(getattr(live_decision, "source_timestamp", "") or "")
    missing = tuple(getattr(live_decision, "missing_fields", ()) or ())
    warnings = tuple(getattr(live_decision, "warnings", ()) or ())
    trajectory = getattr(live_decision, "trajectory", {}) or {}

    if status != "READY":
        decision = "NOT_READY"
        setup = "WAITING FOR EXACT V8"
    elif action == "QUALIFIED":
        decision = "QUALIFIED"
        setup = "QUALIFIED"
    else:
        decision = action
        setup = "WAIT"

    reason_parts = []
    if missing:
        reason_parts.append("Missing: " + ", ".join(str(x) for x in missing))
    if warnings:
        reason_parts.append("Warnings: " + ", ".join(str(x) for x in warnings))
    if not reason_parts:
        reason_parts.append("Authoritative live decision returned by W73 live decision service.")

    return {
        "Decision": decision,
        "Strategy Status": status,
        "Setup State": setup,
        "W73 Maturity": maturity or "—",
        "W73 Variant": variant or "—",
        "Action": action,
        "Strategy Observation Time": observation_timestamp or "—",
        "Source Timestamp": source_timestamp or "—",
        "Missing Fields": ", ".join(str(x) for x in missing) if missing else "—",
        "Warnings": ", ".join(str(x) for x in warnings) if warnings else "—",
        "Trajectory": trajectory,
        "Reason": " ".join(reason_parts),
        "Invalidation": "Fail-closed: no directional action is inferred when exact V8 evidence is incomplete.",
    }


def _alerts(df, evidence, requested_date, data_session, ingest_result, data_asof):
    alerts = []
    now = datetime.now().isoformat(timespec="seconds")
    age = _age_label(data_asof)
    age_sec = _age_seconds(data_asof)

    def add(level, checkpoint, message):
        alerts.append({
            "Level": level,
            "Checkpoint": checkpoint,
            "Message": message,
            "Data time": data_asof,
            "Detected": now,
            "Age": age,
        })

    if ingest_result.get("status") == "ERROR":
        add("CRITICAL", "INGESTION", str(ingest_result.get("error", "Unknown ingestion error")))

    if data_session is None:
        add("WAITING", "SOURCE", f"No source observations available for {requested_date}.")
        return alerts

    if data_session != requested_date:
        add(
            "FALLBACK",
            "SESSION",
            f"{requested_date} unavailable; displaying last valid session {data_session}.",
        )

    if data_session == requested_date and age_sec is not None and age_sec > 900:
        add("STALE", "FRESHNESS", f"Latest live source observation is {age} old.")

    if evidence["symbols"] and evidence["core_pct"] < 95:
        add(
            "DATA QUALITY",
            "EVIDENCE",
            f"Core evidence completeness {evidence['core_pct']:.1f}%.",
        )

    if df.empty:
        add("UNIVERSE", "FILTER", "No qualified stocks at this point in time.")

    if not alerts:
        add("CLEAR", "SYSTEM", "No dashboard-level integrity checkpoint is breached.")

    return alerts



def _fmt_timestamp(value):
    """Compact trader-facing timestamp without changing the underlying value."""
    if value in (None, "", "—", "N/A"):
        return "—"
    return str(value).replace("T", " ")[:19]


def _display_strategy_counts(board_df):
    if board_df is None or board_df.empty or "Decision" not in board_df.columns:
        return {"QUALIFIED": 0, "WAIT": 0, "NOT_READY": 0}
    return {
        "QUALIFIED": int((board_df["Decision"].astype(str) == "QUALIFIED").sum()),
        "WAIT": int((board_df["Decision"].astype(str) == "WAIT").sum()),
        "NOT_READY": int((board_df["Decision"].astype(str) == "NOT_READY").sum()),
    }


def _apply_trader_filters(df, symbol_filter, action_filter, variant_filter,
                          maturity_filter, min_strength, hide_not_ready):
    """Display-only controls; never alter PIT rows, universe evaluation, or strategy logic."""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if symbol_filter:
        needle = str(symbol_filter).strip().upper()
        out = out[out["Symbol"].astype(str).str.upper().str.contains(needle, na=False)]
    if action_filter != "ALL" and "Decision" in out.columns:
        out = out[out["Decision"].astype(str) == action_filter]
    if variant_filter != "ALL" and "W73 Variant" in out.columns:
        out = out[out["W73 Variant"].astype(str) == variant_filter]
    if maturity_filter != "ALL" and "W73 Maturity" in out.columns:
        out = out[out["W73 Maturity"].astype(str) == maturity_filter]
    if "Strength" in out.columns:
        out = out[pd.to_numeric(out["Strength"], errors="coerce").fillna(0) >= int(min_strength)]
    if hide_not_ready and "Decision" in out.columns:
        out = out[out["Decision"].astype(str) != "NOT_READY"]
    return out


def _format_trader_board(df):
    """Trader-facing formatting only; values and timestamps remain unchanged."""
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in ("Source Timestamp", "Strategy Observation Time", "Filter Alert Time",
                "Last Event Time", "Qualified Since"):
        if col in out.columns:
            out[col] = out[col].map(_fmt_timestamp)
    return out


def _style_priority(df):
    styler = df.style

    def pct(v):
        try:
            x = float(v)
            if x > 0:
                return "color:#138a3d;font-weight:700"
            if x < 0:
                return "color:#c62828;font-weight:700"
        except Exception:
            pass
        return ""

    def strength(v):
        try:
            x = float(v)
            if x >= 75:
                return "background-color:#c9efd4;color:#075b2c;font-weight:800"
            if x >= 55:
                return "background-color:#fff0b8;color:#704f00;font-weight:800"
            return "background-color:#edf0f3;color:#58636e;font-weight:700"
        except Exception:
            return ""

    def bias(v):
        s = str(v)
        if "LONG" in s:
            return "background-color:#e1f5e8;color:#117a37;font-weight:800"
        if "SHORT" in s:
            return "background-color:#fde5e5;color:#b21f1f;font-weight:800"
        return "background-color:#fff4d6;color:#806000;font-weight:800"

    def buildup(v):
        s = str(v).lower()
        if "long buildup" in s or "short covering" in s:
            return "color:#117a37;font-weight:700"
        if "short buildup" in s or "long unwinding" in s:
            return "color:#b21f1f;font-weight:700"
        return ""

    for c in ["Price Chg %", "ATM Straddle %"]:
        if c in df.columns:
            styler = styler.map(pct, subset=[c])
    if "Strength" in df.columns:
        styler = styler.map(strength, subset=["Strength"])
    if "Bias" in df.columns:
        styler = styler.map(bias, subset=["Bias"])
    if "Buildup" in df.columns:
        styler = styler.map(buildup, subset=["Buildup"])
    if "OI Chg %" in df.columns:
        styler = styler.map(
            lambda v: "color:#2468a8;font-weight:700" if _num(v) not in (None, 0) else "",
            subset=["OI Chg %"],
        )
    if "Volume Chg (%)" in df.columns:
        styler = styler.map(
            lambda v: "color:#a35a00;font-weight:700" if _num(v) not in (None, 0) else "",
            subset=["Volume Chg (%)"],
        )

    def action(v):
        s = str(v)
        if s == "QUALIFIED":
            return "background-color:#dff4e5;color:#126b37;font-weight:900"
        if s == "WAIT":
            return "background-color:#fff4d6;color:#805900;font-weight:800"
        if s == "NOT_READY":
            return "background-color:#f3f5f7;color:#59636e;font-weight:800"
        return ""

    if "Decision" in df.columns:
        styler = styler.map(action, subset=["Decision"])
    if "Action" in df.columns:
        styler = styler.map(action, subset=["Action"])
    if "Strategy Status" in df.columns:
        styler = styler.map(action, subset=["Strategy Status"])
    return styler


def _style_alerts(df):
    palette = {
        "CRITICAL": ("#fde2e2", "#9b1c1c"),
        "STALE": ("#fde2e2", "#9b1c1c"),
        "DATA QUALITY": ("#fff0d6", "#8a5200"),
        "FALLBACK": ("#fff4d6", "#805900"),
        "WAITING": ("#eef2f6", "#4c5967"),
        "UNIVERSE": ("#e8f0fb", "#245a9b"),
        "CLEAR": ("#e8f7ee", "#126b37"),
    }

    def fmt(v):
        bg, fg = palette.get(str(v), ("#f4f4f4", "#444"))
        return f"background-color:{bg};color:{fg};font-weight:800"

    return df.style.map(fmt, subset=["Level"])


def _render_exact_v8_detail(live_decision, source_row=None):
    """Compact PIT + Exact V8 presentation; never recomputes strategy state."""
    if live_decision is None:
        st.info("No authoritative Exact V8 evaluation is available for this symbol at the current maturity.")
        return

    status = str(getattr(live_decision, "status", "NOT_READY") or "NOT_READY")
    action = str(getattr(live_decision, "action", "NOT_READY") or "NOT_READY")
    variant = getattr(live_decision, "variant", None) or "—"
    maturity = str(getattr(live_decision, "maturity", "") or "—")
    obs_ts = str(getattr(live_decision, "observation_timestamp", "") or "—")
    source_ts = str(getattr(live_decision, "source_timestamp", "") or "—")
    missing = tuple(getattr(live_decision, "missing_fields", ()) or ())
    warnings = tuple(getattr(live_decision, "warnings", ()) or ())
    trajectory = getattr(live_decision, "trajectory", {}) or {}
    features = getattr(live_decision, "feature_vector", {}) or {}
    variant_value = str(getattr(live_decision, "variant", "") or "").upper()
    variants = {"W73-A": variant_value == "W73-A", "W73-B": variant_value == "W73-B"}

    a, b, c, d, e = st.columns(5)
    a.metric("V8 STATUS", status)
    b.metric("ACTION", action)
    c.metric("W73 VARIANT", variant)
    d.metric("MATURITY", maturity)
    e.metric("OBSERVATION", _fmt_timestamp(obs_ts))

    st.markdown("#### PIT / Canonical provenance")
    provenance = {
        "trading_date": getattr(live_decision, "trading_date", None),
        "source_timestamp": source_ts,
        "strategy_observation_timestamp": obs_ts,
        "source_file": source_row.get("_source_file") if source_row else None,
        "canonical_observation_timestamp": source_row.get("_observation_timestamp") if source_row else None,
    }
    if source_row:
        for key in ("_pece_match_status", "_pece_source_file", "_pece_observation_timestamp"):
            if key in source_row:
                provenance[key] = source_row.get(key)
    st.json(provenance)

    left, right = st.columns(2)
    with left:
        st.markdown("#### Exact V8 — 25-field state")
        if features:
            feature_rows = [{"Field": k, "Value": v} for k, v in features.items()]
            st.dataframe(pd.DataFrame(feature_rows), use_container_width=True, hide_index=True, height=430)
        else:
            st.info("Exact V8 feature vector is unavailable because this maturity is NOT_READY.")

    with right:
        st.markdown("#### Frozen W73 / trajectory")
        nl_t3_a = (features.get("orb_agree") == "NO" and features.get("magnitude_count_band") == "0" and trajectory.get("px_negative_count_pre_maturity") is not None and trajectory.get("px_negative_count_pre_maturity") <= 3)
        nl_t3_b = (features.get("orb_price_agree") == "NO" and features.get("magnitude_count_band") == "0" and trajectory.get("px_negative_count_pre_maturity") is not None and trajectory.get("px_negative_count_pre_maturity") <= 3)
        nl_t2_a = (features.get("orb_agree") == "NO" and features.get("magnitude_count_band") == "0" and trajectory.get("px_negative_count_pre_maturity") is not None and trajectory.get("px_negative_count_pre_maturity") <= 2)
        nl_t2_b = (features.get("orb_price_agree") == "NO" and features.get("magnitude_count_band") == "0" and trajectory.get("px_negative_count_pre_maturity") is not None and trajectory.get("px_negative_count_pre_maturity") <= 2)
        st.json({
            "W73-A": bool(variants.get("W73-A", False)),
            "W73-B": bool(variants.get("W73-B", False)),
            "W73-NL": {
                "T3-A": nl_t3_a, "T3-B": nl_t3_b,
                "T2-A": nl_t2_a, "T2-B": nl_t2_b,
                "negative_count_pre_maturity": trajectory.get("px_negative_count_pre_maturity"),
            },
            "trajectory": trajectory,
            "missing_fields": list(missing),
            "warnings": list(warnings),
        })
        if status == "READY" and not any(bool(v) for v in variants.values()) and any((nl_t3_a, nl_t3_b, nl_t2_a, nl_t2_b)):
            st.info("W73-NL — NEXT-LAYER RESEARCH: this stock fails frozen W73-A/B but matches a separately researched T2/T3 condition. This does not alter W73 qualification.")
        st.caption("Display only. Frozen W73-A/B and Exact V8 come from the authoritative live decision service. W73-NL is a separate research classification and does not modify the engine or W73 gates.")


def _evaluate_maturity(rows, trading_date, maturity):
    """Evaluate one frozen W73 checkpoint through the same LiveDecision path.

    This is historical/validation selection only. It does not create new
    maturity checkpoints and does not alter the frozen W73-A/B gates.
    """
    if not rows or not maturity:
        return None, None, []
    try:
        cutoff = datetime.fromisoformat(str(trading_date)).replace(
            hour=int(str(maturity).split(":")[0]),
            minute=int(str(maturity).split(":")[1]),
            second=0,
            microsecond=0,
        )
    except (TypeError, ValueError):
        return None, None, []

    source_truth = set(_source_truth_symbols())
    available = sorted({
        str(r.get("Symbol", "")).strip().upper()
        for r in rows
        if r.get("Symbol") and str(r.get("Symbol", "")).strip().upper() in source_truth
    })
    decisions = []
    for symbol in available:
        symbol_rows = []
        for r in rows:
            if str(r.get("Symbol", "")).strip().upper() != symbol:
                continue
            raw_ts = r.get("_observation_timestamp", r.get("timestamp"))
            try:
                ts = raw_ts if isinstance(raw_ts, datetime) else datetime.fromisoformat(str(raw_ts))
            except (TypeError, ValueError):
                continue
            if ts <= cutoff:
                symbol_rows.append(r)
        if symbol_rows:
            decisions.append(
                evaluate_symbol(
                    symbol_rows,
                    symbol=symbol,
                    trading_date=str(trading_date),
                    maturity=str(maturity),
                    orb_minutes=15,
                )
            )
    return cutoff, str(maturity), decisions


def _post_w73_activity(rows, w73_cutoff="10:15"):
    """Return post-10:15 source activity without creating W73 signals."""
    if not rows:
        return pd.DataFrame()
    try:
        hour, minute = [int(x) for x in str(w73_cutoff).split(":")]
    except (TypeError, ValueError):
        return pd.DataFrame()

    records = []
    for r in rows:
        ts_value = r.get("_observation_timestamp", r.get("timestamp"))
        try:
            ts = ts_value if isinstance(ts_value, datetime) else datetime.fromisoformat(str(ts_value))
        except (TypeError, ValueError):
            continue
        if (ts.hour, ts.minute, ts.second) <= (hour, minute, 0):
            continue
        symbol = str(r.get("Symbol", "")).strip().upper()
        if not symbol:
            continue
        records.append({
            "Symbol": symbol,
            "Post-W73 Time": ts.isoformat(timespec="seconds"),
            "Price Chg %": r.get("Price Chg %", r.get("price_chg_pct", "—")),
            "OI Chg %": r.get("OI Chg %", r.get("oi_chg_pct", "—")),
            "Volume Chg (%)": r.get("Volume Chg (%)", r.get("volume_chg_pct", "—")),
            "IV": r.get("IV", "—"),
            "PCR Chg %": r.get("PCR Chg %", r.get("PCR Chg", "—")),
            "Buildup": r.get("Buildup", "—"),
        })
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["_sort_ts"] = pd.to_datetime(df["Post-W73 Time"], errors="coerce")
    df = df.sort_values(["_sort_ts", "Symbol"], ascending=[False, True])
    return df.drop_duplicates("Symbol", keep="first").drop(columns=["_sort_ts"], errors="ignore")


# Controlled validation reference derived from the previously run W73 shadow
# research. It is displayed for comparison only and never feeds W73 decisions.
# Historical dashboard acceptance baseline — display/validation only.
# Source: the previously run 23/24/25-Sep shadow W73 + softened NL research.
# It NEVER feeds LiveDecision, W73-A/B, or any trading action.
# Values are sets by layer at the frozen maturity checkpoint.
VALIDATION_REFERENCE = {
    # Layer-specific acceptance baseline. Empty sets are intentional test cases.
    ("2026-09-23", "09:45"): {"W73-A": {"SAIL"}, "W73-B": set(), "NEXT-LAYER": set()},
    ("2026-09-23", "10:00"): {"W73-A": {"SAIL"}, "W73-B": {"UPL"}, "NEXT-LAYER": set()},
    ("2026-09-23", "10:15"): {"W73-A": {"SAIL"}, "W73-B": set(), "NEXT-LAYER": set()},
    ("2026-09-24", "09:45"): {"W73-A": set(), "W73-B": set(), "NEXT-LAYER": set()},
    ("2026-09-24", "10:00"): {"W73-A": set(), "W73-B": set(), "NEXT-LAYER": set()},
    ("2026-09-24", "10:15"): {"W73-A": set(), "W73-B": set(), "NEXT-LAYER": set()},
    ("2026-09-25", "09:45"): {"W73-A": {"FORTIS", "MAXHEALTH"}, "W73-B": set(), "NEXT-LAYER": {"ZYDUSLIFE", "RADICO"}},
    ("2026-09-25", "10:00"): {"W73-A": {"ADANIPOWER"}, "W73-B": set(), "NEXT-LAYER": set()},
    ("2026-09-25", "10:15"): {"W73-A": {"ADANIPOWER"}, "W73-B": set(), "NEXT-LAYER": {"ASIANPAINT"}},
}


# ---------------------------------------------------------------------
# Isolated 25-Sep POC proof panel
# ---------------------------------------------------------------------
# This section is deliberately independent of the LIVE Trading Date control.
# It reads the fixed 2026-09-25 PIT cache, evaluates only the five historically
# established POC symbols at the four frozen maturities, and never feeds the
# live queue, LiveDecision state, alerts, or trading action.
POC_25SEP_BASKET = (
    "BANDHANBNK",
    "MOTILALOFS",
    "POLICYBZR",
    "RADICO",
    "SAIL",
)
POC_25SEP_DATE = "2026-09-25"
POC_25SEP_MATURITIES = ("09:30", "09:45", "10:00", "10:15")
POC_25SEP_PROVENANCE = (
    "Original 25-Sep POC basket established by the earlier controlled W73 analysis. "
    "This panel is historical/read-only; current layer/status is evaluated through "
    "the same Exact V8 / LiveDecision path and never injected into the live queue."
)


def _poc_nl_flags(decision):
    features = getattr(decision, "feature_vector", {}) or {}
    trajectory = getattr(decision, "trajectory", {}) or {}
    status = str(getattr(decision, "status", "NOT_READY") or "NOT_READY").upper()
    variant = str(getattr(decision, "variant", "") or "").upper()
    neg = trajectory.get("px_negative_count_pre_maturity")
    try:
        neg = int(neg) if neg is not None else None
    except (TypeError, ValueError):
        neg = None
    base = status == "READY" and variant not in {"W73-A", "W73-B"}
    t3a = base and features.get("orb_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg is not None and neg <= 3
    t3b = base and features.get("orb_price_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg is not None and neg <= 3
    t2a = base and features.get("orb_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg is not None and neg <= 2
    t2b = base and features.get("orb_price_agree") == "NO" and features.get("magnitude_count_band") == "0" and neg is not None and neg <= 2
    return t3a, t3b, t2a, t2b, neg


def _poc_layer(decision):
    if decision is None:
        return "NOT_READY", "NOT_READY", "—", None
    status = str(getattr(decision, "status", "NOT_READY") or "NOT_READY").upper()
    action = str(getattr(decision, "action", "NOT_READY") or "NOT_READY").upper()
    variant = str(getattr(decision, "variant", "") or "").upper()
    t3a, t3b, t2a, t2b, neg = _poc_nl_flags(decision)
    if status != "READY":
        return "NOT_READY", status, "—", neg
    if variant in {"W73-A", "W73-B"}:
        return variant, status, variant, neg
    if t2a:
        return "W73-NL", status, "T2-A", neg
    if t2b:
        return "W73-NL", status, "T2-B", neg
    if t3a:
        return "W73-NL", status, "T3-A", neg
    if t3b:
        return "W73-NL", status, "T3-B", neg
    return "READY-NONMATCH", status, "—", neg


def _render_25sep_poc_panel():
    """Render the fixed 25-Sep POC independently from live controls."""
    st.markdown("### Historical POC — 25-Sep-2026 · Isolated Proof")
    st.caption(POC_25SEP_PROVENANCE)

    poc_cache = CACHE_ROOT / f"{POC_25SEP_DATE}.jsonl"
    if not poc_cache.exists():
        st.info(f"Historical POC cache is not available: {poc_cache}")
        return

    try:
        poc_rows_all = load_rows(poc_cache)
    except Exception as exc:
        st.error(f"Unable to read isolated 25-Sep POC cache: {type(exc).__name__}: {exc}")
        return

    poc_rows = [
        r for r in poc_rows_all
        if str(r.get("Symbol", "")).strip().upper() in POC_25SEP_BASKET
    ]
    if not poc_rows:
        st.info("No PIT rows are available for the established five-stock POC basket.")
        return

    records = []
    for maturity in POC_25SEP_MATURITIES:
        _, _, decisions = _evaluate_maturity(poc_rows, POC_25SEP_DATE, maturity)
        dm = {str(getattr(d, "symbol", "")).upper(): d for d in decisions}
        for symbol in POC_25SEP_BASKET:
            d = dm.get(symbol)
            layer, status, rule, neg = _poc_layer(d)
            records.append({
                "MATURITY": maturity,
                "SYMBOL": symbol,
                "STATUS": status,
                "LAYER": layer,
                "W73": getattr(d, "variant", None) or "—",
                "NL RULE": rule,
                "NEG PRE-MATURITY": neg if neg is not None else "—",
                "MISSING": ", ".join(str(x) for x in (getattr(d, "missing_fields", ()) or ())) or "—",
                "OBS": _fmt_timestamp(getattr(d, "observation_timestamp", "") or "—"),
            })

    poc_df = pd.DataFrame(records)
    qualified = int(poc_df["LAYER"].isin(["W73-A", "W73-B"]).sum())
    nl = int((poc_df["LAYER"] == "W73-NL").sum())
    not_ready = int((poc_df["LAYER"] == "NOT_READY").sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("POC STOCKS", len(POC_25SEP_BASKET))
    c2.metric("W73-A/B HITS", qualified)
    c3.metric("W73-NL HITS", nl)
    c4.metric("NOT_READY CELLS", not_ready)

    shown = poc_df.copy()
    st.dataframe(shown, use_container_width=True, hide_index=True, height=330)
    st.caption(
        "Fixed historical date/checkpoints only. No current Trading Date selection is used. "
        "No historical row is written into the live queue. Missing remains missing; "
        "W73-A/B gates remain frozen."
    )


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------
with st.sidebar:
    st.header("W73 Controls")
    trading_date = st.text_input("Trading date", datetime.now().strftime("%Y-%m-%d"))
    month = st.text_input("Source month", "September26")
    auto_refresh = st.checkbox("Live auto refresh", value=True)
    refresh = st.number_input("Refresh seconds", min_value=30, max_value=300, value=60, step=15)
    refresh_now = st.button("Refresh now", use_container_width=True)

    st.markdown("### Decision View")
    view_mode = st.radio(
        "Trader Layer",
        ["VALIDATION", "READY", "NEXT-LAYER RESEARCH", "NOT_READY", "ALL / AUDIT"],
        horizontal=True,
        help="Display-only. W73-NL never modifies frozen W73-A/B."
    )
    evaluation_checkpoint = st.selectbox(
        "W73 checkpoint",
        ["AUTO / latest elapsed", "09:30", "09:45", "10:00", "10:15"],
        help="Only the four frozen W73 maturities are valid."
    )
    symbol_filter = st.text_input("Symbol", value="", placeholder="e.g. RELIANCE")
    variant_filter = st.selectbox("W73 gate", ["ALL", "W73-A", "W73-B"])
    action_filter = st.selectbox("Decision", ["ALL", "QUALIFIED", "NEXT-LAYER RESEARCH", "READY / OTHER", "NOT_READY"])
    max_rows = st.number_input("Rows", min_value=5, max_value=50, value=20)
    min_strength = st.slider("Min strength", 0, 100, 0, 5)
    hide_not_ready = st.checkbox("Hide NOT_READY", value=False)
    st.caption(f"READ ONLY: {source_root()}")
    st.caption("Controls are secondary. Sidebar starts collapsed; use the native arrow only when needed.")




def _build_validation_reference_board(board_df, expected_layers, qualification_map=None):
    """Reference-only three-layer acceptance board with FIRST ALERT visibility."""
    if not expected_layers:
        return pd.DataFrame()
    current = {}
    if board_df is not None and not board_df.empty and "Symbol" in board_df.columns:
        for row in board_df.to_dict("records"):
            current[str(row.get("Symbol", "")).strip().upper()] = row
    qualification_map = qualification_map or {}
    records = []
    for expected_layer in ("W73-A", "W73-B", "NEXT-LAYER"):
        for symbol in sorted(expected_layers.get(expected_layer, set())):
            cur = current.get(symbol, {})
            q = qualification_map.get(symbol, {})
            current_layer = str(cur.get("Layer", "NOT FOUND") or "NOT FOUND")
            current_variant = str(cur.get("W73 Variant", "—") or "—")
            if current_layer == "W73-A/B":
                actual_layer = current_variant if current_variant in ("W73-A", "W73-B") else current_layer
            elif current_layer == "W73-NL":
                actual_layer = "NEXT-LAYER"
            else:
                actual_layer = current_layer
            records.append({
                "Symbol": symbol,
                "FIRST ALERT": cur.get("Filter Alert Time", q.get("Filter Alert Time", "—")),
                "EXPECTED LAYER": expected_layer,
                "CURRENT LAYER": actual_layer,
                "CURRENT DECISION": str(cur.get("Decision", "NOT FOUND") or "NOT FOUND"),
                "W73 VARIANT": current_variant,
                "STRENGTH": cur.get("Strength", q.get("Entry Strength", "—")),
                "OBS TIME": cur.get("Strategy Observation Time", "—"),
                "LAST EVENT TIME": cur.get("Last Event Time", "—"),
                "VALIDATION": "MATCH" if actual_layer == expected_layer else "MISMATCH / NOT REPRODUCED",
            })
    return pd.DataFrame(records)


def _render_live_board():
    # ---------------------------------------------------------------------
    # Ingestion
    # ---------------------------------------------------------------------
    try:
        ingest_result = ingest(trading_date, month, CACHE_ROOT)
    except Exception as exc:
        ingest_result = {
            "status": "ERROR",
            "trading_date": trading_date,
            "new_rows": 0,
            "new_symbols": 0,
            "new_intervals": [],
            "error": str(exc),
        }

    requested_cache = CACHE_ROOT / f"{trading_date}.jsonl"
    current_rows = load_rows(requested_cache) if requested_cache.exists() else []

    if current_rows and _has_authoritative_source(trading_date, month):
        data_session = trading_date
        active_cache = requested_cache
        rows = current_rows
        session_mode = "LIVE"
    else:
        data_session, prior_cache, prior_rows = _find_latest_prior_cache(trading_date, month)
        if prior_rows:
            active_cache = prior_cache
            rows = prior_rows
            session_mode = "FALLBACK"
        else:
            active_cache = requested_cache
            rows = []
            session_mode = "WAITING"

    # Exact V8 live-decision service is authoritative for signal readiness.
    # It fails closed when the required ORB/V8 evidence is unavailable.
    # The active data session is authoritative when the requested date falls
    # back to a prior trading session (e.g. weekend/holiday).
    decision_date = data_session or trading_date
    if evaluation_checkpoint == "AUTO / latest elapsed":
        live_decision_asof, live_maturity, live_decisions = evaluate_latest_maturity(
            rows,
            trading_date=decision_date,
            symbols=_source_truth_symbols(),
            orb_minutes=15,
        )
        evaluation_mode = "AUTO / latest elapsed"
    else:
        live_decision_asof, live_maturity, live_decisions = _evaluate_maturity(
            rows,
            decision_date,
            evaluation_checkpoint,
        )
        evaluation_mode = f"HISTORICAL CHECKPOINT {evaluation_checkpoint}"
    # Historical checkpoint must be a true point-in-time board.  Never combine
    # a historical LiveDecision with later raw rows merely for display.
    board_rows = _rows_asof(rows, live_decision_asof or data_asof)
    live_decision_counts = decision_summary(live_decisions)
    live_decision_map = {
        str(getattr(d, "symbol", "")).upper(): d
        for d in live_decisions
        if str(getattr(d, "symbol", "")).strip()
    }
    # Frozen decision vocabulary: incomplete exact V8 evidence remains NOT_READY.
    # This is display/contract vocabulary only; it does not relax signal qualification.
    NOT_READY = "NOT_READY"
    legacy_board_df, latest_rows = _build_board(board_rows)
    # Main trader population comes from authoritative Exact V8/LiveDecision
    # results, not the separate universe-priority filter. This exposes every
    # READY stock while keeping W73-NL visibly separate from frozen W73-A/B.
    board_df = _build_research_layer_board(live_decisions, board_rows)
    qualification_map = _first_qualification(rows, live_decision_asof or data_asof)
    event_map = _qualification_events(rows, live_decision_asof or data_asof)
    evidence = _evidence_metrics(latest_rows)
    times = _observation_times(rows)
    data_asof = max(times) if times else "N/A"
    if not board_df.empty:
        board_df["Filter Alert Time"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: qualification_map.get(s, {}).get("Filter Alert Time", qualification_map.get(s, {}).get("Qualified Since", "—")))
        board_df["Qualified Since"] = board_df["Filter Alert Time"]
        board_df["Entry Strength"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: qualification_map.get(s, {}).get("Entry Strength", 0))
        board_df["Entry Evidence"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: qualification_map.get(s, {}).get("Entry Evidence", "—"))
        board_df["Qualification Age"] = board_df["Filter Alert Time"].map(lambda ts: _duration_label(ts, data_asof))
        board_df["_live_decision"] = board_df["Symbol"].astype(str).str.upper().map(live_decision_map)
        strategy_rows = board_df.apply(
            lambda row: _strategy_decision(row, row.get("_live_decision")),
            axis=1,
            result_type="expand",
        )

        # Merge strategy display fields into the authoritative board instead of
        # concatenating DataFrames side-by-side.  The research-layer board
        # already owns fields such as Decision, Strategy Status, Bias,
        # Strength and Filter Alert Time.  A horizontal concat would create
        # duplicate column names and Streamlit rejects those tables.
        #
        # Preserve the board's authoritative layer Decision; the remaining
        # strategy-service fields are assigned by name so each column remains
        # unique.
        if "Decision" in strategy_rows.columns:
            strategy_rows = strategy_rows.drop(columns=["Decision"])

        for column in strategy_rows.columns:
            board_df[column] = strategy_rows[column].to_numpy()

        board_df = board_df.drop(columns=["_live_decision"], errors="ignore")

        if board_df.columns.duplicated().any():
            duplicate_columns = board_df.columns[board_df.columns.duplicated()].tolist()
            raise RuntimeError(
                "W73 dashboard internal error: duplicate board columns after "
                f"strategy merge: {duplicate_columns}"
            )
        board_df["Last Event"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: _event_summary(s, event_map, data_asof)[0])
        board_df["Last Event Time"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: _event_summary(s, event_map, data_asof)[1])
    age = _age_label(data_asof)
    evaluated_count = len(board_df)
    ready_count = int((board_df["Strategy Status"].astype(str).str.upper() == "READY").sum()) if "Strategy Status" in board_df.columns else 0
    qualified_count = int((board_df["Layer"].astype(str) == "W73-A/B").sum()) if "Layer" in board_df.columns else 0
    up, down, flat = _direction_counts(board_df)
    alerts = _alerts(board_df, evidence, trading_date, data_session, ingest_result, data_asof)
    strategy_counts = {
        "QUALIFIED": int(live_decision_counts.get("QUALIFIED", 0)),
        "WAIT": int(live_decision_counts.get("WAIT", 0)),
        "NOT_READY": int(live_decision_counts.get("NOT_READY", 0)),
    }
    if live_maturity:
        st.session_state["w73_live_decision_summary"] = {
            "maturity": live_maturity,
            "asof": str(live_decision_asof) if live_decision_asof else None,
            **live_decision_counts,
        }

    # Explicit readiness gate: never claim the final intraday strategy is ready
    # unless the exact V8 fields required by the frozen candidate exist in the
    # current point-in-time observations.
    # Readiness is based on the authoritative LiveDecision results, not on
    # derived V8 fields being embedded in raw PIT observations.
    exact_ready_count = sum(
        1 for d in live_decisions
        if str(getattr(d, "status", "")).upper() == "READY"
    )
    not_ready_count = sum(
        1 for d in live_decisions
        if str(getattr(d, "status", "")).upper() != "READY"
    )
    # Evaluator readiness is separate from per-symbol evidence readiness.
    # A NOT_READY symbol fails closed for itself; it must not invalidate other symbols.
    exact_v8_present = bool(live_decisions)
    w73_strategy_evaluation_ready = bool(live_decisions)
    live_session_ready = data_session == trading_date and bool(latest_rows)
    universe_ready = bool(UNIVERSE_CONFIG.exists()) and bool(board_df is not None)
    ingestion_ready = ingest_result.get("status") == "OK"
    qualified_live_count = int(
        sum(1 for d in live_decisions if str(getattr(d, "action", "")).upper() == "QUALIFIED")
    )
    final_strategy_ready = (
        live_session_ready
        and universe_ready
        and ingestion_ready
        and qualified_live_count > 0
    )



    # ---------------------------------------------------------------------
    # Header
    # ---------------------------------------------------------------------
    st.title("NTIS W73 — Intraday Trader Board")
    st.caption("Decision-first • frozen W73 09:30/09:45/10:00/10:15 • separate next-layer research • exact PIT timestamps")

    badge = {
        "LIVE": ("🟢", "LIVE"),
        "FALLBACK": ("🟠", "FALLBACK — PRIOR SESSION"),
        "WAITING": ("⚪", "WAITING FOR SOURCE"),
    }.get(session_mode, ("🔴", "ERROR"))
    st.markdown(f"### {badge[0]} {badge[1]}")

    if session_mode == "FALLBACK":
        st.warning(
            f"{trading_date} source data has not arrived. Showing {data_session} only as a READ-ONLY fallback. "
            "It will automatically switch to today's live session when the first source interval arrives."
        )
    elif session_mode == "WAITING":
        st.info(
            f"No source data yet for {trading_date}. The board will populate automatically at the first source interval."
        )


    # ---------------------------------------------------------------------
    # Trader KPI ribbon — one compact hierarchy, no duplicate readiness block.
    # ---------------------------------------------------------------------
    layer_counts = {
        "W73": int(sum(1 for d in live_decisions if str(getattr(d, "status", "")).upper() == "READY" and str(getattr(d, "variant", "") or "").upper() in {"W73-A", "W73-B"})),
        "NL": int(sum(1 for r in board_df.to_dict("records") if r.get("Layer") == "W73-NL")),
        "NOT_READY": int(sum(1 for d in live_decisions if str(getattr(d, "status", "")).upper() != "READY")),
    }
    k = st.columns(7)
    k[0].metric("EVALUATED", len(live_decisions))
    k[1].metric("W73-A/B READY", layer_counts["W73"])
    k[2].metric("NEXT-LAYER", layer_counts["NL"])
    k[3].metric("NOT_READY", layer_counts["NOT_READY"])
    k[4].metric("EXACT V8", "READY" if exact_v8_present else "NOT READY")
    k[5].metric("MATURITY", live_maturity or "—")
    k[6].metric("DATA SESSION", data_session or "—")

    st.markdown(
        f'<div class="w73-session-strip">'
        f'<span class="w73-live-dot">●</span> LIVE DATA '
        f'&nbsp;|&nbsp; Session <b>{data_session or "—"}</b> '
        f'&nbsp;|&nbsp; Source <b>{_fmt_timestamp(data_asof)}</b> '
        f'&nbsp;|&nbsp; Age <b>{age}</b> '
        f'&nbsp;|&nbsp; W73 checkpoint <b>{live_maturity or "—"}</b>'
        f'&nbsp;|&nbsp; Mode <b>{evaluation_mode}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Contract label retained for dashboard restoration tests: Intraday Setup Readiness.
    # ---------------------------------------------------------------------
    # Trader display view + compact readiness rail
    # ---------------------------------------------------------------------
    # Compatibility display filter: checkpoint selection above is the real
    # W73 evaluation control. Keep this as ALL so it cannot alter PIT semantics.
    maturity_filter = "ALL"
    filtered_board = _apply_trader_filters(
        board_df,
        symbol_filter,
        action_filter,
        variant_filter,
        maturity_filter,
        min_strength,
        hide_not_ready,
    )

    # Empty authoritative board is valid while waiting for source/decisions.
    # Never access Layer until decision rows exist.
    if not filtered_board.empty and "Layer" in filtered_board.columns:
        if view_mode == "VALIDATION":
            filtered_board = filtered_board[filtered_board["Layer"].isin(["W73-A/B", "W73-NL"])]
        elif view_mode == "READY":
            filtered_board = filtered_board[filtered_board["Layer"].isin(["W73-A/B", "READY-NONMATCH"])]
        elif view_mode == "NEXT-LAYER RESEARCH":
            filtered_board = filtered_board[filtered_board["Layer"] == "W73-NL"]
        elif view_mode == "NOT_READY":
            filtered_board = filtered_board[filtered_board["Layer"] == "NOT_READY"]
    # ALL / AUDIT leaves the full authoritative population intact.
    filtered_board = filtered_board.head(int(max_rows))

    # Post-W73 activity is deliberately separate from frozen W73-A/B.
    post_w73_df = _post_w73_activity(rows, "10:15")

    # Controlled validation reference: display-only, never feeds decisions.
    ref_key = (str(decision_date), str(live_maturity or ""))
    expected_layers = VALIDATION_REFERENCE.get(ref_key, {"W73-A": set(), "W73-B": set(), "NEXT-LAYER": set()})
    expected_a = set(expected_layers.get("W73-A", set()))
    expected_b = set(expected_layers.get("W73-B", set()))
    expected_nl = set(expected_layers.get("NEXT-LAYER", set()))
    expected_w73 = expected_a | expected_b

    actual_a = {str(r.get("Symbol", "")).upper() for r in board_df.to_dict("records") if str(r.get("Layer", "")) == "W73-A/B" and str(r.get("W73 Variant", "")) == "W73-A"}
    actual_b = {str(r.get("Symbol", "")).upper() for r in board_df.to_dict("records") if str(r.get("Layer", "")) == "W73-A/B" and str(r.get("W73 Variant", "")) == "W73-B"}
    actual_nl = {str(r.get("Symbol", "")).upper() for r in board_df.to_dict("records") if str(r.get("Layer", "")) == "W73-NL"}
    actual_w73 = actual_a | actual_b
    validation_applicable = ref_key in VALIDATION_REFERENCE
    validation_pass = validation_applicable and actual_a == expected_a and actual_b == expected_b and actual_nl == expected_nl
    expected_symbols = expected_w73 | expected_nl
    actual_symbols = actual_w73 | actual_nl
    validation_board = _build_validation_reference_board(board_df, expected_layers, qualification_map)

    main_col, rail_col = st.columns([5.8, 1.35], gap="small")

    with main_col:
        st.subheader(
            "Historical Validation — 23/24/25-Sep Source-of-Truth"
            if view_mode == "VALIDATION"
            else "Decision Board — Intraday Eye View"
        )

        if view_mode == "VALIDATION":
            display_df = validation_board.copy()
            if not display_df.empty:
                for c in ("FIRST ALERT", "OBS TIME", "LAST EVENT TIME"):
                    if c in display_df.columns:
                        display_df[c] = display_df[c].map(_fmt_timestamp)
                expected_count = len(expected_symbols)
                reproduced_count = len(actual_symbols & expected_symbols)
                missing_count = len(expected_symbols - actual_symbols)
                unexpected_count = len(actual_symbols - expected_symbols)
                vc = st.columns(4)
                vc[0].metric("W73-A", len(expected_a))
                vc[1].metric("W73-B", len(expected_b))
                vc[2].metric("NEXT-LAYER", len(expected_nl))
                vc[3].metric("MATCHED", reproduced_count)

                display_cols = [
                    "Symbol", "FIRST ALERT", "EXPECTED LAYER", "CURRENT LAYER", "CURRENT DECISION",
                    "W73 VARIANT", "STRENGTH", "OBS TIME",
                    "LAST EVENT TIME", "VALIDATION",
                ]
                display_cols = [c for c in display_cols if c in display_df.columns]
                st.dataframe(
                    display_df[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    height=340,
                )
                st.markdown('<div class="w73-acceptance-head">FIRST ALERT → 3-LAYER ACCEPTANCE PROOF</div>', unsafe_allow_html=True)
                st.caption("Every historically identified candidate is shown across W73-A, W73-B and NEXT-LAYER. FIRST ALERT is the source-backed earliest filter qualification timestamp; reference rows never create signals.")
            else:
                display_df = pd.DataFrame()
                st.info(
                    f"No expected W73/NL candidates are recorded for {decision_date} @ {live_maturity}. "
                    "An empty reference set is itself a valid historical test case."
                )
        else:
            display_df = filtered_board.copy()
            if not display_df.empty:
                cols = [
                    "Symbol", "Layer", "Decision", "W73 Variant", "NL-T3-A", "NL-T3-B",
                    "NL-T2-A", "NL-T2-B", "Strength", "Bias", "Filter Alert Time",
                    "Strategy Observation Time", "Last Event", "Last Event Time",
                ]
                cols = [c for c in cols if c in display_df.columns]
                shown = display_df[cols].copy().rename(columns={
                    "Filter Alert Time": "FIRST ALERT",
                    "Strategy Observation Time": "OBS TIME",
                    "Last Event": "LAST EVENT",
                    "Last Event Time": "LAST EVENT TIME",
                })
                for c in ("FIRST ALERT", "OBS TIME", "LAST EVENT TIME"):
                    if c in shown.columns:
                        shown[c] = shown[c].map(_fmt_timestamp)
                if "Strength" in shown.columns:
                    shown["Strength"] = pd.to_numeric(
                        shown["Strength"], errors="coerce"
                    ).fillna(0).astype(int).astype(str) + "/100"
                st.dataframe(
                    shown.head(int(max_rows)),
                    use_container_width=True,
                    hide_index=True,
                    height=340,
                )
                st.caption(
                    "FIRST ALERT = first exact source timestamp for filter eligibility. "
                    "OBS TIME = authoritative PIT maturity observation. "
                    "W73-NL is separate research and never modifies frozen W73-A/B."
                )
            else:
                st.info("No stocks match the current decision filters.")

        validation_state = (
            "PASS" if validation_pass else
            "MISMATCH" if validation_applicable else
            "N/A — LIVE / NO HISTORICAL BASELINE"
        )
        validation_detail = (
            f"A expected: {', '.join(sorted(expected_a)) or 'NONE'} | got: {', '.join(sorted(actual_a)) or 'NONE'}"
            f" &nbsp; • &nbsp; B expected: {', '.join(sorted(expected_b)) or 'NONE'} | got: {', '.join(sorted(actual_b)) or 'NONE'}"
            f" &nbsp; • &nbsp; NEXT-LAYER expected: {', '.join(sorted(expected_nl)) or 'NONE'} | got: {', '.join(sorted(actual_nl)) or 'NONE'}"
        ) if validation_applicable else (
            "No frozen 23/24/25-Sep acceptance baseline is attached to this session/checkpoint."
        )
        st.markdown(
            f'<div class="w73-validation"><b>HISTORICAL VALIDATION · {validation_state}</b><br>{validation_detail}</div>',
            unsafe_allow_html=True,
        )

    with rail_col:
        st.markdown("#### Decision Focus")

        selected_symbol = None
        if not display_df.empty:
            selected_symbol = st.selectbox(
                "Stock",
                display_df["Symbol"].astype(str).tolist(),
                key="decision_focus_symbol",
                label_visibility="collapsed",
            )
            selected_row = display_df[display_df["Symbol"].astype(str) == selected_symbol].iloc[0]
            selected_decision = live_decision_map.get(selected_symbol.upper())
            decision = str(selected_row.get("CURRENT DECISION", selected_row.get("Decision", "NOT_READY")))
            variant = str(selected_row.get("W73 VARIANT", selected_row.get("W73 Variant", "—")))
            strength_value = selected_row.get("STRENGTH", selected_row.get("Strength", 0))
            try:
                strength = int(float(strength_value))
            except (TypeError, ValueError):
                strength = 0
            bias = str(selected_row.get("Bias", "WATCH"))
            first_alert = _fmt_timestamp(selected_row.get("FIRST ALERT", selected_row.get("Filter Alert Time", "—")))
            obs_time = _fmt_timestamp(selected_row.get("OBS TIME", selected_row.get("Strategy Observation Time", "—")))
            source_time = _fmt_timestamp(selected_row.get("Source Timestamp", "—"))
            reason = str(selected_row.get("CURRENT REASON", selected_row.get("Reason", "—")))
            expected_layer_focus = str(selected_row.get("EXPECTED LAYER", selected_row.get("EXPECTED", "")))
            current_layer_focus = str(selected_row.get("CURRENT LAYER", selected_row.get("Layer", "—")))

            nl_rule = "—"
            if bool(selected_row.get("NL-T3-A", False)): nl_rule = "T3-A"
            elif bool(selected_row.get("NL-T3-B", False)): nl_rule = "T3-B"
            elif bool(selected_row.get("NL-T2-A", False)): nl_rule = "T2-A"
            elif bool(selected_row.get("NL-T2-B", False)): nl_rule = "T2-B"
            gate_label = variant if variant in ("W73-A","W73-B") else (f"W73-NL {nl_rule}" if nl_rule != "—" else "NO MATCH")
            st.markdown(
                f'<div class="w73-decision-card">'
                f'<div class="w73-decision-symbol">{selected_symbol}</div>'
                f'<div class="w73-decision-state">{decision} · {selected_row.get("CURRENT LAYER", selected_row.get("Layer", "—"))}</div>'
                f'<div class="w73-critical"><b>STRENGTH</b> {strength}/100 · <b>BIAS</b> {bias}</div>'
                f'<div class="w73-critical w73-first-alert"><b>FIRST ALERT</b> {first_alert}</div>'
                f'<div class="w73-critical"><b>OBS</b> {obs_time}</div>'
                f'<div class="w73-critical"><b>SOURCE</b> {source_time}</div>'
                f'<div class="w73-critical"><b>EXPECTED</b> {expected_layer_focus or "—"} · <b>GATE</b> {gate_label}</div>'
                f'<div class="w73-critical"><b>NEG PRE-MATURITY</b> {selected_row.get("NL Negative Count", "—")}</div>'
                f'<div class="w73-critical"><b>REASON</b> {reason}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Only the decision-critical gates are shown in the trader view.
            if view_mode == "VALIDATION":
                validation_match = str(selected_row.get("VALIDATION", "")).upper() == "MATCH"
                validation_detail = (
                    "Current engine reproduces the expected historical layer."
                    if validation_match else
                    f"Expected {expected_layer_focus or '—'}; current result is {current_layer_focus or '—'}."
                )
                gate_rows = [
                    ("EXPECTED", expected_layer_focus or "—", "Historical reference only."),
                    ("CURRENT", current_layer_focus or "—", validation_detail),
                    ("EXACT V8", "READY" if str(getattr(selected_decision, "status", "")).upper() == "READY" else "NOT READY",
                     f"Maturity {getattr(selected_decision, 'maturity', '—')}" if selected_decision else "No current LiveDecision."),
                    ("VALIDATION", "MATCH" if validation_match else "MISMATCH",
                     "Reference-only acceptance comparison; never creates a signal."),
                ]
            else:
                gate_rows = [
                    ("FILTER", "PASS" if first_alert != "—" else "WAIT", "First filter qualification timestamp available." if first_alert != "—" else "No filter qualification yet."),
                    ("EXACT V8", "READY" if str(getattr(selected_decision, "status", "")).upper() == "READY" else "NOT READY",
                     f"Maturity {getattr(selected_decision, 'maturity', '—')}" if selected_decision else "No LiveDecision."),
                    ("W73 GATE", "QUALIFIED" if variant in ("W73-A","W73-B") else "NO MATCH",
                     "Frozen A/B match." if variant in ("W73-A","W73-B") else "Does not change W73."),
                    ("DECISION", decision, "Authoritative LiveDecision action."),
                ]
            for name, status, detail in gate_rows:
                cls = "w73-gate-ready" if status in ("PASS","READY","QUALIFIED") else ("w73-gate-fail" if status in ("NO MATCH","NOT_READY") else "w73-gate-wait")
                st.markdown(
                    f'<div class="w73-gate"><div class="{cls}">● <b>{name}</b><strong>{status}</strong></div>'
                    f'<div class="w73-gate-detail">{detail}</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Select a validation candidate or current decision row to inspect the decision-critical state.")

        if validation_applicable:
            st.markdown(
                f'<div class="w73-mini-panel"><b>Validation @ {live_maturity}</b><br>'
                f'W73: {", ".join(sorted(expected_w73)) or "NONE"}<br>'
                f'NL: {", ".join(sorted(expected_nl)) or "NONE"}<br>'
                f'Current: {"PASS" if validation_pass else "MISMATCH"}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("#### Decision Counts")
        for label, count in [
            ("W73-A/B", layer_counts["W73"]),
            ("NEXT-LAYER", layer_counts["NL"]),
            ("NOT_READY", layer_counts["NOT_READY"]),
        ]:
            st.markdown(f'<div class="w73-summary-label"><span>{label}</span><b>{count}</b></div>', unsafe_allow_html=True)

        st.markdown("#### Post-W73 Activity")
        if not post_w73_df.empty:
            compact_post = post_w73_df[["Symbol","Post-W73 Time","Price Chg %"]].copy()
            compact_post = compact_post.rename(columns={"Post-W73 Time":"TIME","Price Chg %":"PRICE %"})
            compact_post["TIME"] = compact_post["TIME"].map(_fmt_timestamp)
            st.dataframe(compact_post.head(8), use_container_width=True, hide_index=True, height=150)
        else:
            st.caption("No post-10:15 observations yet.")


    # ---------------------------------------------------------------------
    # Post-W73 monitoring data is displayed compactly in the right rail.
    # It remains separate from frozen W73-A/B.
    # ---------------------------------------------------------------------


    # ---------------------------------------------------------------------

    # ---------------------------------------------------------------------
    # Fixed historical POC section. It is intentionally outside the live
    # decision-board selection logic and never changes live queue state.
    _render_25sep_poc_panel()

    # ---------------------------------------------------------------------
    # Secondary audit panels — collapsed by default so the trader viewport
    # remains one-screen and decision-first.
    # ---------------------------------------------------------------------
    with st.expander("Diagnostics — PIT / Exact V8 / Lineage / Audit", expanded=False, key="w73_diagnostics_v1"):
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Alerts & timestamps", "PIT / Exact V8", "Lineage", "Universe health"]
        )

        with tab1:
            st.subheader("Alerts / timestamps")
            st.caption(
                "FIRST ALERT is the first exact source timestamp for filter eligibility. "
                "Dashboard detected time is separate."
            )
            if not board_df.empty:
                stock_alerts = board_df[[
                    "Symbol", "Decision", "Strategy Status", "Bias", "Strength",
                    "Filter Alert Time", "Qualification Age", "Last Event",
                    "Last Event Time", "Entry Evidence"
                ]].copy()
                stock_alerts = stock_alerts.rename(columns={
                    "Filter Alert Time": "FIRST ALERT",
                    "Entry Evidence": "FILTER EVIDENCE",
                    "Last Event Time": "LAST EVENT TIME"
                })
                st.dataframe(stock_alerts.head(int(max_rows)), use_container_width=True, hide_index=True)
            st.dataframe(_style_alerts(pd.DataFrame(alerts)), use_container_width=True, hide_index=True)

        with tab2:
            st.subheader("Selected Stock — PIT / Exact V8 / Frozen W73")
            if not filtered_board.empty:
                selected = st.selectbox("Priority stock", filtered_board["Symbol"].astype(str).tolist(), key="pit_v8_symbol")
                r = filtered_board[filtered_board["Symbol"].astype(str) == selected].iloc[0]
                source_row = next((x for x in latest_rows if str(x.get("Symbol", "")).upper() == selected.upper()), None)
                live_decision = live_decision_map.get(selected.upper())
                _render_exact_v8_detail(live_decision, source_row)
                a, b, c, d = st.columns(4)
                a.metric("Decision", r.get("Decision", "NO TRADE"))
                b.metric("Bias", r.get("Bias", "WATCH"))
                c.metric("Strength", f"{int(r.get('Strength', 0))}/100")
                d.metric("FIRST ALERT", _fmt_timestamp(r.get("Filter Alert Time", "—")))
                st.write(f"**Why it qualified:** {r.get('Entry Evidence', '—')}")
                st.write(f"**Decision reason:** {r.get('Reason', '—')}")

        with tab3:
            st.subheader("Point-in-Time Lineage")
            st.json({
                "requested_trading_date": trading_date,
                "actual_data_session": data_session,
                "session_mode": session_mode,
                "data_as_of": data_asof,
                "evaluation_checkpoint": evaluation_checkpoint,
                "evaluation_mode": evaluation_mode,
                "live_decision_service": {
                    "maturity": live_maturity,
                    "asof": str(live_decision_asof) if live_decision_asof else None,
                    "summary": live_decision_counts,
                },
                "timestamp_contract": {
                    "source_timestamp": "Authoritative source observation timestamp.",
                    "strategy_observation_timestamp": "LiveDecision maturity observation timestamp.",
                    "dashboard_detected_timestamp": datetime.now().isoformat(timespec="seconds"),
                },
                "active_cache": str(active_cache),
                "requested_cache": str(requested_cache),
                "source_intervals": len(times),
                "evaluated_stocks": evaluated_count,
                "w73_ab_qualified_stocks": qualified_count,
                "post_w73_activity_symbols": int(len(post_w73_df)),
                "source_root": str(source_root()),
                "ingest_result": ingest_result,
            })

        with tab4:
            st.subheader("Filter / Selection Audit")
            if not filtered_board.empty:
                audit_cols = [
                    "Symbol", "Decision", "Strategy Status", "Filter Alert Time",
                    "Qualification Age", "Entry Strength", "Priority", "Bias",
                    "Strength", "Entry Evidence",
                ]
                audit_cols = [c for c in audit_cols if c in board_df.columns]
                st.dataframe(filtered_board[audit_cols].head(int(max_rows)), use_container_width=True, hide_index=True)
            st.caption(
                f"Universe health: {evaluated_count} evaluated / {evidence['symbols']} observed symbols; "
                f"core evidence completeness {evidence['core_pct']:.1f}%."
            )



# ---------------------------------------------------------------------
# Main dashboard render — failure-safe.
#
# The trader pane must never become completely blank while the sidebar
# remains visible. Any runtime failure is surfaced inside the main pane
# with the exact exception and the active checkpoint/session context.
# This wrapper does not change W73 or NL decisions.
# ---------------------------------------------------------------------
_render_started = st.empty()

try:
    if hasattr(st, "fragment"):
        # Historical validation must be stable: no periodic rerun/fading.
        # Live AUTO mode alone receives the timed refresh.
        run_every = int(refresh) if (auto_refresh and evaluation_checkpoint == "AUTO / latest elapsed") else None
        _render_live_board_fragment = st.fragment(run_every=run_every)(_render_live_board)
        _render_live_board_fragment()
    else:
        _render_live_board()

    _render_started.empty()

except Exception as _dashboard_exc:
    _render_started.markdown(
        """
        <div style="
            margin:.5rem 0;
            padding:12px 14px;
            border:1px solid #7b2d35;
            border-radius:7px;
            background:#160d13;
            color:#f2d9dd;">
            <div style="font-size:1rem;font-weight:800;color:#ff6875;">
                W73 DASHBOARD RENDER ERROR
            </div>
            <div style="margin-top:5px;font-size:.72rem;">
                The trader pane stopped during rendering. No trading decision is
                inferred from this failure and the W73 engine has not been modified.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.error(f"{type(_dashboard_exc).__name__}: {_dashboard_exc}")
    with st.expander("Technical traceback / deployment diagnostic", expanded=True):
        st.code(
            "Trading date: " + str(trading_date) + "\n"
            "Source month: " + str(month) + "\n"
            "W73 checkpoint: " + str(evaluation_checkpoint) + "\n"
            "Trader layer: " + str(view_mode) + "\n"
            "Python: " + sys.executable + "\n\n"
            + repr(_dashboard_exc),
            language="text",
        )

if refresh_now:
    st.rerun()

