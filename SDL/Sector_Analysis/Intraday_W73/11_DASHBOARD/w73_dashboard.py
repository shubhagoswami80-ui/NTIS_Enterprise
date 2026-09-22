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

from w73_live_ingestor import ingest, source_root
from w73_point_in_time_service import load_rows, latest_as_of
from w73_universe_engine import load_config, evaluate
from w73_live_decision_service import evaluate_latest_maturity, decision_summary


st.set_page_config(
    page_title="NTIS W73 — Intraday Trader Board",
    page_icon="W73",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CACHE_ROOT = ROOT / "07_OUTPUT" / "live_cache"
UNIVERSE_CONFIG = ROOT / "07_OUTPUT" / "universe_config.json"


# ---------------------------------------------------------------------
# Trader-board UI
# ---------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding: .65rem .8rem .7rem .8rem; max-width: 100%;}
h1 {font-size: 1.55rem !important; margin: 0 0 .05rem 0 !important;}
h2 {font-size: 1.0rem !important; margin: .45rem 0 .25rem 0 !important;}
h3 {font-size: .9rem !important;}
div[data-testid="stMetric"] {padding:.12rem .28rem;border:1px solid rgba(128,128,128,.16);border-radius:6px;}
div[data-testid="stMetricLabel"] {font-size:.65rem !important;}
div[data-testid="stMetricValue"] {font-size:1.02rem !important;}
div[data-testid="stDataFrame"] {border-radius:6px;}
.small-note {font-size:.68rem;opacity:.72;}
.bias-long {color:#117a37;font-weight:800;}
.bias-short {color:#b21f1f;font-weight:800;}
.bias-watch {color:#806000;font-weight:800;}
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


def _find_latest_prior_cache(requested_date: str):
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



def _first_qualification(rows):
    """Return the first exact source timestamp at which each symbol became eligible."""
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

def _qualification_events(rows):
    """Derive point-in-time universe state transitions from cached intervals."""
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


def _strategy_decision(row):
    return _validated_strategy_gate(row)


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


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------
with st.sidebar:
    st.header("W73 Controls")
    trading_date = st.text_input("Trading date", datetime.now().strftime("%Y-%m-%d"))
    month = st.text_input("Source month", "September26")
    auto_refresh = st.checkbox("Auto refresh", value=True)
    refresh = st.number_input("Refresh interval (seconds)", min_value=30, max_value=300, value=60, step=15)
    refresh_now = st.button("Refresh now", use_container_width=True)
    max_rows = st.number_input("Priority stocks", min_value=5, max_value=30, value=15)
    st.caption(f"READ ONLY source: {source_root()}")
    st.caption("30s default. 5s full-page reruns are intentionally disabled.")



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

    if current_rows:
        data_session = trading_date
        active_cache = requested_cache
        rows = current_rows
        session_mode = "LIVE"
    else:
        data_session, prior_cache, prior_rows = _find_latest_prior_cache(trading_date)
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
    live_decision_asof, live_maturity, live_decisions = evaluate_latest_maturity(
        rows,
        trading_date=trading_date,
        orb_minutes=15,
    )
    live_decision_counts = decision_summary(live_decisions)
    # Frozen decision vocabulary: incomplete exact V8 evidence remains NOT_READY.
    # This is display/contract vocabulary only; it does not relax signal qualification.
    NOT_READY = "NOT_READY"
    board_df, latest_rows = _build_board(rows)
    qualification_map = _first_qualification(rows)
    event_map = _qualification_events(rows)
    evidence = _evidence_metrics(latest_rows)
    times = _observation_times(rows)
    data_asof = max(times) if times else "N/A"
    if not board_df.empty:
        board_df["Filter Alert Time"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: qualification_map.get(s, {}).get("Filter Alert Time", qualification_map.get(s, {}).get("Qualified Since", "—")))
        board_df["Qualified Since"] = board_df["Filter Alert Time"]
        board_df["Entry Strength"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: qualification_map.get(s, {}).get("Entry Strength", 0))
        board_df["Entry Evidence"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: qualification_map.get(s, {}).get("Entry Evidence", "—"))
        board_df["Qualification Age"] = board_df["Filter Alert Time"].map(lambda ts: _duration_label(ts, data_asof))
        strategy_rows = board_df.apply(_strategy_decision, axis=1, result_type="expand")
        board_df = pd.concat([board_df.reset_index(drop=True), strategy_rows.reset_index(drop=True)], axis=1)
        board_df["Last Event"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: _event_summary(s, event_map, data_asof)[0])
        board_df["Last Event Time"] = board_df["Symbol"].astype(str).str.upper().map(lambda s: _event_summary(s, event_map, data_asof)[1])
    age = _age_label(data_asof)
    qualified_count = len(board_df)
    up, down, flat = _direction_counts(board_df)
    alerts = _alerts(board_df, evidence, trading_date, data_session, ingest_result, data_asof)
    if live_maturity:
        st.session_state["w73_live_decision_summary"] = {
            "maturity": live_maturity,
            "asof": str(live_decision_asof) if live_decision_asof else None,
            **live_decision_counts,
        }

    # Explicit readiness gate: never claim the final intraday strategy is ready
    # unless the exact V8 fields required by the frozen candidate exist in the
    # current point-in-time observations.
    required_v8 = [
        "orb_agree",
        "magnitude_count_band",
        "px_all_negative_pre_maturity",
        "strategy_family",
    ]
    exact_v8_present = bool(latest_rows) and all(
        key in latest_rows[0] for key in required_v8
    )
    live_session_ready = data_session == trading_date and bool(latest_rows)
    universe_ready = bool(UNIVERSE_CONFIG.exists()) and bool(board_df is not None)
    ingestion_ready = ingest_result.get("status") == "OK"
    final_strategy_ready = live_session_ready and universe_ready and ingestion_ready and exact_v8_present



    # ---------------------------------------------------------------------
    # Header
    # ---------------------------------------------------------------------
    st.title("NTIS W73 — Intraday Trader Board")
    st.caption("Decision-first • qualified universe • evidence strength • exact event timestamps • port 9005")

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
    # At-a-glance market / session strip
    # ---------------------------------------------------------------------
    s = st.columns(9)
    s[0].metric("DATA SESSION", data_session or "—")
    s[1].metric("DATA TIME", data_asof)
    s[2].metric("AGE", age)
    s[3].metric("INTERVALS", len(times))
    s[4].metric("QUALIFIED", qualified_count if rows else "—")
    s[5].metric("UP", up)
    s[6].metric("DOWN", down)
    s[7].metric("EVIDENCE", f"{evidence['core_pct']:.0f}%")

    strategy_statuses = board_df["Strategy Status"].value_counts().to_dict() if not board_df.empty else {}
    actionable = sum(1 for x in board_df.get("Decision", []) if str(x) in ("BUY", "SELL")) if not board_df.empty else 0
    s[8].metric("ACTIONABLE", actionable)

    st.markdown(
        '<div class="small-note">Data Time = source observation timestamp. '
        'Detected/alert time is separate. No prior-session observation is relabelled as today.</div>',
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------------------
    # Setup readiness — explicit, conservative, non-deceptive.
    # ---------------------------------------------------------------------
    st.subheader("Intraday Setup Readiness")
    readiness = pd.DataFrame([
        ["Source ingestion", "READY" if ingestion_ready else "NOT READY",
         "Latest source interval can be read." if ingestion_ready else "Ingestion returned an error."],
        ["Point-in-time cache", "READY" if bool(latest_rows) else "WAITING",
         f"{len(times)} source intervals available." if latest_rows else "No point-in-time observations available."],
        ["Filtered universe", "READY" if universe_ready and qualified_count > 0 else "WAITING",
         f"{qualified_count} stocks currently qualify." if qualified_count else "No stock currently qualifies."],
        ["Today's live session", "READY" if live_session_ready else "WAITING",
         f"Using {data_session}." if data_session else "Waiting for today's first source interval."],
        ["Exact V8 strategy fields", "READY" if exact_v8_present else "NOT READY",
         "All frozen candidate fields are present." if exact_v8_present else "Exact V8 trajectory fields are not in the live cache."],
        ["Validated BUY/SELL engine", "NOT DEPLOYED",
         "No validated directional BUY/SELL rule is being inferred from the 65/100 evidence meter."],
        ["FINAL TRADING READINESS", "READY" if final_strategy_ready else "NOT READY",
         "All required live strategy inputs are present." if final_strategy_ready else "Do not treat the current board as an executable BUY/SELL signal."],
    ], columns=["Checkpoint", "Status", "Interpretation"])

    def _readiness_style(df):
        def s(v):
            if v == "READY":
                return "background-color:#e5f5e9;color:#126b37;font-weight:800"
            if v in ("NOT READY", "NOT DEPLOYED"):
                return "background-color:#fde8e8;color:#9b1c1c;font-weight:800"
            return "background-color:#fff4d6;color:#805900;font-weight:800"
        return df.style.map(s, subset=["Status"])

    st.dataframe(_readiness_style(readiness), use_container_width=True, hide_index=True, height=270)

    # ---------------------------------------------------------------------
    # What to watch / strongest candidates
    # ---------------------------------------------------------------------
    st.subheader("What to Watch Now")

    if not board_df.empty:
        top = board_df.head(3)
        cards = st.columns(3)
        for col, (_, r) in zip(cards, top.iterrows()):
            bias = str(r.get("Bias", "WATCH"))
            strength = int(r.get("Strength", 0))
            symbol = str(r.get("Symbol", "—"))
            meter = str(r.get("Strength Meter", ""))
            evidence_text = str(r.get("Evidence", ""))
            qualified_since = str(r.get("Qualified Since", "—"))
            decision = str(r.get("Decision", "NO TRADE"))
            strategy_status = str(r.get("Strategy Status", "NOT DEPLOYED"))
            if "LONG" in bias:
                color = "#117a37"
            elif "SHORT" in bias:
                color = "#b21f1f"
            else:
                color = "#806000"

            col.markdown(
                f"""
                <div style="border:1px solid rgba(128,128,128,.22);border-radius:8px;padding:10px;
                            min-height:118px;background:rgba(128,128,128,.025)">
                  <div style="font-size:1.05rem;font-weight:800">{symbol}</div>
                  <div style="color:{color};font-weight:800">{bias} · {strength}/100</div>
                  <div style="font-family:monospace;letter-spacing:1px">{meter}</div>
                  <div style="font-size:.74rem;font-weight:800;margin-top:3px">DECISION: {decision}</div>
                  <div style="font-size:.67rem">Strategy: {strategy_status}</div>
                  <div style="font-size:.70rem;margin-top:3px">FILTER ALERT: {qualified_since}</div>
                  <div style="font-size:.70rem;margin-top:3px">{evidence_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No qualified candidates are available yet.")


    # ---------------------------------------------------------------------
    # Main actionable priority board
    # ---------------------------------------------------------------------
    st.subheader("Priority Stocks — Select the Strongest Evidence")

    if not board_df.empty:
        cols = [
            "Symbol", "Decision", "Setup State", "Bias", "Strength", "Strength Meter",
            "Filter Alert Time", "Qualification Age", "Last Event", "Last Event Time",
            "Evidence", "Price Chg %", "OI Chg %", "Volume Chg (%)",
        ]
        cols = [c for c in cols if c in board_df.columns]
        shown = board_df[cols].head(int(max_rows)).copy()

        st.dataframe(
            _style_priority(shown),
            use_container_width=True,
            hide_index=True,
            height=540,
        )

        st.caption(
            "Decision is generated only by the frozen strategy gate when exact V8 fields are available. "
            "Strength is evidence prioritisation, not probability. Filter Alert Time is the exact first qualifying source timestamp."
        )
    else:
        st.info("No qualified stocks are available at this point in time.")


    # ---------------------------------------------------------------------
    # Secondary panels
    # ---------------------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Alerts & timestamps", "Stock evidence", "Lineage", "Universe health"]
    )

    with tab1:
        st.subheader("Alerts / Checkpoints")
        st.caption("FILTER ALERT TIME = exact source interval when the stock first satisfied the configured W73 universe rule. DETECTED TIME is a separate dashboard event time.")
        if not board_df.empty:
            stock_alerts = board_df[["Symbol", "Decision", "Strategy Status", "Bias", "Strength", "Filter Alert Time", "Qualification Age", "Last Event", "Last Event Time", "Entry Evidence"]].copy()
            stock_alerts = stock_alerts.rename(columns={"Filter Alert Time": "FILTER ALERT TIME", "Entry Evidence": "FILTER EVIDENCE", "Last Event Time": "LAST EVENT TIME"})
            st.dataframe(stock_alerts.head(int(max_rows)), use_container_width=True, hide_index=True, height=300)
        alert_df = pd.DataFrame(alerts)
        st.dataframe(
            _style_alerts(alert_df),
            use_container_width=True,
            hide_index=True,
            height=min(330, 90 + 45 * len(alert_df)),
        )
        st.caption("FILTER ALERT TIME is the exact market-data/source timestamp. DETECTED is the dashboard processing/checkpoint timestamp; they are never substituted for each other.")

    with tab2:
        st.subheader("Selected Stock — Why is it strong?")
        if not board_df.empty:
            selected = st.selectbox("Priority stock", board_df["Symbol"].astype(str).tolist())
            r = board_df[board_df["Symbol"].astype(str) == selected].iloc[0]

            a, b, c, d, e = st.columns(5)
            a.metric("Decision", r.get("Decision", "NO TRADE"))
            b.metric("Bias", r.get("Bias", "WATCH"))
            c.metric("Current strength", f"{int(r.get('Strength', 0))}/100")
            d.metric("FILTER ALERT TIME", r.get("Filter Alert Time", "—"))
            e.metric("Qualification age", r.get("Qualification Age", "—"))

            st.markdown(f"**Filter alert time:** `{r.get('Filter Alert Time', '—')}` — exact source timestamp of first qualification.")
            st.markdown(f"**Why it qualified:** {r.get('Entry Evidence', '—')}")
            st.markdown(f"**Current evidence:** {r.get('Evidence', '—')}")
            st.markdown(f"**Strategy status:** `{r.get('Strategy Status', 'NOT DEPLOYED')}`")
            st.markdown(f"**Decision reason:** {r.get('Reason', '—')}")
            st.markdown(f"**Invalidation:** {r.get('Invalidation', '—')}")
            st.progress(min(100, int(r.get("Strength", 0))) / 100)

            st.markdown(
                "**Interpretation:** price direction + price/OI relationship + buildup + "
                "participation/volume + supporting PCR/IV evidence. Missing fields are not treated as zero."
            )
        else:
            st.info("No qualified stock available.")

    with tab3:
        st.subheader("Point-in-Time Lineage")
        st.json({
            "requested_trading_date": trading_date,
            "actual_data_session": data_session,
            "session_mode": session_mode,
            "data_as_of": data_asof,
            "data_age": age,
            "filter_alert_timestamp_definition": "First exact source observation timestamp at which the configured universe rule returned eligible=True for the stock.",
            "event_timeline_definition": "QUALIFIED, RE-QUALIFIED, and INVALIDATED transitions are derived chronologically from cached source intervals.",
            "validated_strategy_gate": "Frozen V8_PLUS_TRAJECTORY candidate is evaluated only when all exact live fields exist; otherwise status is NOT EVALUABLE.",
            "active_cache": str(active_cache),
            "requested_cache": str(requested_cache),
            "source_intervals": len(times),
            "qualified_stocks": qualified_count,
            "source_root": str(source_root()),
            "ingest_result": ingest_result,
            "detected_at": datetime.now().isoformat(timespec="seconds"),
            "fallback_rule": "Prior cache is display-only and never copied into requested-date cache.",
        })

    with tab4:
        st.subheader("Filter / Selection Audit")
        st.caption("This panel answers when each stock first became qualified by the configured point-in-time universe rule.")
        if not board_df.empty:
            audit_cols = [
                "Symbol", "Decision", "Strategy Status", "Filter Alert Time",
                "Qualification Age", "Entry Strength", "Priority", "Bias",
                "Strength", "Entry Evidence",
            ]
            audit_cols = [c for c in audit_cols if c in board_df.columns]
            st.dataframe(
                board_df[audit_cols].head(int(max_rows)),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No stocks have qualified in the available point-in-time cache.")

        st.markdown(
            f"**Universe health:** {qualified_count} qualified / {evidence['symbols']} observed symbols; "
            f"core evidence completeness {evidence['core_pct']:.1f}%."
        )




if hasattr(st, "fragment"):
    _render_live_board_fragment = st.fragment(run_every=(int(refresh) if auto_refresh else None))(_render_live_board)
    _render_live_board_fragment()
else:
    _render_live_board()

if refresh_now:
    st.rerun()
