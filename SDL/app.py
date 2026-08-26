from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import EVENT_CSV
from pipeline import (
    discover_historical_snapshots,
    process_latest_snapshot_for_today,
    replay_trading_date,
    replay_all_available,
    process_snapshot,
)
from prediction_engine import build_current_predictions
from source_loader import parse_observation_timestamp
from storage import load_events


st.set_page_config(
    page_title="SDL — Straddle Breakout Decision Center",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background:#f7f8fc; }
    .block-container { max-width:1420px; padding-top:1rem; padding-bottom:1.2rem; }
    .sdl-header { background:linear-gradient(105deg,#0d1830 0%,#17264b 62%,#243a72 100%);
        color:white;padding:18px 22px;border-radius:12px;margin-bottom:12px; }
    .sdl-title { font-size:25px;font-weight:760;margin:0; }
    .sdl-subtitle { font-size:12px;opacity:.88;margin-top:4px; }
    .card { background:white;border:1px solid #e6e9f1;border-radius:11px;padding:13px 15px;margin:9px 0;
        box-shadow:0 3px 12px rgba(20,34,72,.045); }
    .card-title { color:#17233f;font-size:17px;font-weight:740;margin-bottom:5px; }
    .card-subtitle { color:#737c90;font-size:11px;margin-bottom:9px; }
    .metric { background:#fbfcff;border:1px solid #e6e9f1;border-radius:9px;padding:10px 12px;min-height:68px; }
    .metric-label { color:#747d90;font-size:9px;font-weight:760;letter-spacing:.06em;text-transform:uppercase; }
    .metric-value { color:#17233f;font-size:20px;font-weight:760;margin-top:3px; }
    .metric-detail { color:#7c8495;font-size:10px; }
    .decision-up { background:#e8f7ee;border-color:#b9e5c9;color:#146c3b; }
    .decision-down { background:#fff0f0;border-color:#efc2c2;color:#982020; }
    .decision-watch { background:#fff6df;border-color:#f0d59d;color:#8b5a00; }
    .decision-main { font-size:18px;font-weight:780; }
    .decision-meta { font-size:11px;margin-top:4px;opacity:.85; }
    div.stButton > button[kind="primary"] { background:linear-gradient(90deg,#5844d8,#6c4ee6);
        border:0;border-radius:9px;font-weight:700;min-height:40px; }
    div.stButton > button { border-radius:9px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _events() -> pd.DataFrame:
    df = load_events(EVENT_CSV)
    return df.copy() if df is not None else pd.DataFrame()


def _source_timestamp(path: Path) -> pd.Timestamp:
    try:
        return parse_observation_timestamp(path)
    except Exception:
        try:
            return pd.Timestamp.fromtimestamp(path.stat().st_mtime)
        except Exception:
            return pd.NaT


def _available_source_dates() -> list[str]:
    try:
        files = [Path(p) for p in discover_historical_snapshots()]
    except Exception:
        return []
    dates = []
    for p in files:
        ts = _source_timestamp(p)
        if pd.notna(ts):
            dates.append(ts.date().isoformat())
    return sorted(set(dates), reverse=True)


def _latest_source() -> tuple[Path | None, pd.Timestamp | None]:
    today = pd.Timestamp.now().date().isoformat()
    try:
        files = [Path(p) for p in discover_historical_snapshots(today)]
    except Exception:
        return None, None
    valid = [(Path(p), _source_timestamp(Path(p))) for p in files]
    valid = [(p, ts) for p, ts in valid if pd.notna(ts)]
    return max(valid, key=lambda x: x[1]) if valid else (None, None)


def _snapshots_for_date(trading_date: str) -> list[Path]:
    try:
        files = [Path(p) for p in discover_historical_snapshots(trading_date)]
    except Exception:
        return []
    valid = [(p, _source_timestamp(p)) for p in files]
    valid = [(p, ts) for p, ts in valid if pd.notna(ts)]
    valid.sort(key=lambda x: (x[1], str(x[0]).lower()))
    return [p for p, _ in valid]


def _replay_exact_snapshot(path: Path):
    ts = _source_timestamp(path)
    if pd.isna(ts):
        raise ValueError(f"Cannot determine source observation timestamp: {path.name}")
    return process_snapshot(path, ts)


def _store_replay_state(events_result, snapshot: Path, snapshot_df: pd.DataFrame) -> None:
    st.session_state["sdl_replay_events"] = (
        events_result.copy() if isinstance(events_result, pd.DataFrame) else pd.DataFrame()
    )
    st.session_state["sdl_replay_snapshot_df"] = (
        snapshot_df.copy() if isinstance(snapshot_df, pd.DataFrame) else pd.DataFrame()
    )
    st.session_state["sdl_replay_timestamp"] = _source_timestamp(snapshot)


def _replay_state() -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp | None]:
    events = st.session_state.get("sdl_replay_events", pd.DataFrame())
    snap = st.session_state.get("sdl_replay_snapshot_df", pd.DataFrame())
    ts = pd.to_datetime(st.session_state.get("sdl_replay_timestamp"), errors="coerce")
    return events.copy(), snap.copy(), ts


def _base_map_from_snapshot(df: pd.DataFrame) -> dict:
    if df.empty or "Symbol" not in df.columns:
        return {}
    result = {}
    for _, r in df.drop_duplicates("Symbol").iterrows():
        symbol = str(r.get("Symbol", "")).strip().upper()
        if not symbol:
            continue
        op = pd.to_numeric(r.get("daily_open_reference"), errors="coerce")
        prem = pd.to_numeric(r.get("opening_straddle_premium"), errors="coerce")
        if pd.isna(op) or pd.isna(prem) or prem <= 0:
            continue
        result[symbol] = {
            "open_price": float(op),
            "opening_straddle_premium": float(prem),
            "opening_atm_straddle_pct": r.get("opening_atm_straddle_pct"),
        }
    return result


def _decision_candidates(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    if snapshot_df.empty:
        return pd.DataFrame()
    base = _base_map_from_snapshot(snapshot_df)
    return build_current_predictions(snapshot_df, base)


def _decision_style(row):
    d = str(row.get("DECISION", "")).upper()
    if "BULLISH" in d:
        bg, fg = "#e8f7ee", "#146c3b"
    elif "BEARISH" in d:
        bg, fg = "#fff0f0", "#982020"
    else:
        bg, fg = "#fff6df", "#8b5a00"
    return [f"background-color:{bg};color:{fg};font-weight:700;" if c in {"DECISION","STAGE"} else "" for c in row.index]


def _queue(candidates: pd.DataFrame, key: str) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    options = [
        "All", "Bullish", "Bearish", "25%+", "50%+", "75%+",
        "Approaching 100%", "100% Breakout", "Strong", "Developing", "Wait",
    ]
    selected = st.radio("Show", options, horizontal=True, key=key)
    out = candidates.copy()

    if selected == "Bullish":
        out = out[out["direction_label"].eq("BULLISH")]
    elif selected == "Bearish":
        out = out[out["direction_label"].eq("BEARISH")]
    elif selected == "Strong":
        out = out[out["strength_label"].eq("STRONG")]
    elif selected == "Developing":
        out = out[out["strength_label"].eq("DEVELOPING")]
    elif selected == "Wait":
        out = out[out["strength_label"].isin(["WAIT", "WAIT / CONFLICT"])]
    elif selected == "25%+":
        out = out[out["progress"].ge(25)]
    elif selected == "50%+":
        out = out[out["progress"].ge(50)]
    elif selected == "75%+":
        out = out[out["progress"].ge(75)]
    elif selected == "Approaching 100%":
        out = out[out["progress"].ge(75) & out["progress"].lt(100)]
    elif selected == "100% Breakout":
        out = out[out["factual_breakout"]]

    rows = []
    for _, r in out.iterrows():
        rows.append({
            "SYMBOL": r["symbol"],
            "DECISION": r["decision"],
            "PRICE MOVE %": r["signed_price_move_pct"],
            "STRADDLE MOVE %": r["progress"],
            "STAGE": r["stage"],
            "FROZEN STRADDLE ₹": r["frozen_straddle"],
            "BREAKOUT": "YES" if r["factual_breakout"] else "—",
            "STRENGTH": r["strength"],
            "CONFIRMATION": r["strength_label"],
        })
    q = pd.DataFrame(rows)
    if not q.empty:
        q["_break"] = out["factual_breakout"].to_numpy()
        q["_strength"] = out["strength"].to_numpy()
        q["_progress"] = out["progress"].to_numpy()
        q = q.sort_values(
            ["_break", "_strength", "_progress"],
            ascending=[False, False, False],
        ).drop(columns=["_break", "_strength", "_progress"])
    return q.reset_index(drop=True)


def _evidence_table(row: pd.Series) -> pd.DataFrame:
    mapping = [
        ("Price Chg %", "Price Chg %"),
        ("Futures OI Chg %", "OI Chg %"),
        ("CE OI Chg %", "Tot CE OI Chg %"),
        ("PE OI Chg %", "Tot PE OI Chg %"),
        ("PE−CE OI Chg", "Tot PE-CE OI Chg"),
        ("IV Chg %", "IV Chg %"),
        ("PCR Chg %", "PCR Chg %"),
    ]
    rec = []
    for label, key in mapping:
        v = row.get(key, pd.NA)
        rec.append({"EVIDENCE": label, "VALUE": v if pd.notna(v) else "MISSING"})
    return pd.DataFrame(rec)


def _historical_intelligence(events: pd.DataFrame, trading_date: str | None = None):
    """Presentation-only transformation of existing factual first-breakout events."""
    if events is None or events.empty:
        return pd.DataFrame(), pd.DataFrame()

    hist = events.copy()
    hist["trading_date"] = hist.get("trading_date", "").astype(str).str[:10]
    hist["observation_timestamp"] = pd.to_datetime(
        hist.get("observation_timestamp"), errors="coerce"
    )

    for col in [
        "open_price", "current_price", "opening_straddle_premium",
        "expected_1x_price", "breakout_distance", "price_chg_pct",
        "oi_chg_pct", "ce_oi_chg_pct", "pe_oi_chg_pct",
        "pe_minus_ce_oi_chg", "iv_chg_pct", "pcr_chg_pct",
    ]:
        if col in hist.columns:
            hist[col] = pd.to_numeric(hist[col], errors="coerce")

    # These are display metrics only; they do not alter event selection.
    hist["straddle_progress_pct"] = (
        (hist["current_price"] - hist["open_price"]).abs()
        / hist["opening_straddle_premium"].replace(0, pd.NA)
        * 100.0
    )
    hist["beyond_100_pct"] = hist["straddle_progress_pct"] - 100.0

    hist["stage"] = "BREAKOUT"
    hist.loc[hist["straddle_progress_pct"].ge(125), "stage"] = "EXTENDED"
    hist.loc[
        hist["straddle_progress_pct"].ge(100)
        & hist["straddle_progress_pct"].lt(125),
        "stage",
    ] = "BREAKOUT+"

    hist["direction_display"] = hist["direction"].map(
        {"UP": "🟢 UP", "DOWN": "🔴 DOWN"}
    ).fillna(hist["direction"].astype(str))

    # Keep today's view separate from the historical archive.
    if trading_date:
        today = hist[hist["trading_date"].eq(str(trading_date)[:10])].copy()
        archive = hist[~hist["trading_date"].eq(str(trading_date)[:10])].copy()
    else:
        today = hist.iloc[0:0].copy()
        archive = hist.copy()

    # Latest/strongest events first. Missing timestamps stay at bottom.
    for frame in (today, archive):
        if not frame.empty:
            frame["_ts_sort"] = frame["observation_timestamp"].fillna(pd.Timestamp.min)
            frame["_progress_sort"] = frame["straddle_progress_pct"].fillna(-1)
            frame.sort_values(
                ["_ts_sort", "_progress_sort"],
                ascending=[False, False],
                inplace=True,
            )
            frame.drop(columns=["_ts_sort", "_progress_sort"], inplace=True)

    return today, archive


def _render_breakout_table(frame: pd.DataFrame, compact: bool = True):
    if frame.empty:
        return

    display = pd.DataFrame({
        "TIME": frame["observation_timestamp"].dt.strftime("%H:%M:%S").fillna("—"),
        "STOCK": frame["symbol"],
        "DIRECTION": frame["direction_display"],
        "STAGE": frame["stage"],
        "STRADDLE %": frame["straddle_progress_pct"].map(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
        ),
        "PRICE MOVE": frame["price_chg_pct"].map(
            lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
        ),
        "BEYOND 100%": frame["beyond_100_pct"].map(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
        ),
        "BREAKOUT DIST ₹": frame["breakout_distance"].map(
            lambda x: f"{x:+.2f}" if pd.notna(x) else "—"
        ),
    })

    if not compact:
        display["OPEN"] = frame["open_price"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
        display["CMP"] = frame["current_price"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
        display["FROZEN S ₹"] = frame["opening_straddle_premium"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
        display["EVIDENCE"] = frame["oi_chg_pct"].map(lambda x: f"OI {x:+.2f}%" if pd.notna(x) else "OI —")

    st.dataframe(display, width="stretch", hide_index=True)


st.markdown(
    """
    <div class="sdl-header">
      <div class="sdl-title">SDL — Straddle Breakout Decision Center</div>
      <div class="sdl-subtitle">
        ±0.75% price gate → 25/50/75/100% of frozen straddle → confirmation → strength priority
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">CONTROLLED PROCESSING & REPLAY</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Existing SDL pipeline is reused. Source workbooks are read-only. '
    'Replay decisions are evaluated only at the selected timestamp.</div>',
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns([1.1, 1.25, 1.1])
with c1:
    if st.button("▶ PROCESS LATEST", type="primary", width="stretch"):
        try:
            latest, _, _, note = process_latest_snapshot_for_today()
            if latest is None:
                st.warning(note)
            else:
                st.success(f"Processed {latest.name}")
                st.caption(note)
                st.rerun()
        except Exception as exc:
            st.error(f"Processing failed: {exc}")

available_dates = _available_source_dates()
with c2:
    replay_date = st.selectbox(
        "Replay trading date", available_dates,
        format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y"),
        key="sdl_replay_date",
    ) if available_dates else None

with c3:
    if st.button("↻ REPLAY DAY", width="stretch", disabled=not bool(replay_date)):
        try:
            result = replay_trading_date(replay_date)
            st.session_state.pop("sdl_replay_events", None)
            st.session_state.pop("sdl_replay_snapshot_df", None)
            st.session_state.pop("sdl_replay_timestamp", None)
            st.success(
                f"Replayed {result['trading_date']} · {result['files']} files · "
                f"{result['events']} first-breakout events"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Replay day failed: {exc}")

if replay_date:
    snapshots = _snapshots_for_date(replay_date)
    if snapshots:
        selected_snapshot_key = st.selectbox(
            "Exact source snapshot",
            [str(p) for p in snapshots],
            format_func=lambda x: f"{_source_timestamp(Path(x)).strftime('%d %b %Y, %H:%M:%S')} | {Path(x).name}",
            key="sdl_exact_snapshot",
        )
        selected_snapshot = Path(selected_snapshot_key)
        if st.button("↻ REPLAY EXACT SNAPSHOT", type="primary", width="stretch"):
            try:
                events_result, snapshot_df, processed_at = _replay_exact_snapshot(selected_snapshot)
                _store_replay_state(events_result, selected_snapshot, snapshot_df)
                st.success(f"Exact snapshot replayed: {selected_snapshot.name}")
                st.rerun()
            except Exception as exc:
                st.error(f"Exact snapshot replay failed: {exc}")
    else:
        st.info("No timestamped SDL snapshots were discovered for the selected date.")

st.markdown("</div>", unsafe_allow_html=True)

events = _events()
latest_source, latest_ts = _latest_source()

# Active trading date for presentation:
# prefer the selected replay timestamp, otherwise the latest discovered source
# date, otherwise the machine date. This keeps the evidence view useful when
# the latest available source day is not the machine's calendar day.
_replay_state_ts = pd.to_datetime(
    st.session_state.get("sdl_replay_timestamp"), errors="coerce"
)
if pd.notna(_replay_state_ts):
    active_trading_date = _replay_state_ts.date().isoformat()
elif pd.notna(latest_ts):
    active_trading_date = latest_ts.date().isoformat()
else:
    active_trading_date = pd.Timestamp.now().date().isoformat()

today_iso = active_trading_date
today_events = (
    events[events.get("trading_date", pd.Series(dtype=str)).astype(str).str[:10].eq(today_iso)]
    if not events.empty else pd.DataFrame()
)

# LIVE: re-read/process the latest source through the existing pipeline so the
# Decision Center sees early candidates, not only historical first-breakout events.
live_df = pd.DataFrame()
if latest_source is not None:
    try:
        _, live_df, _ = _replay_exact_snapshot(latest_source)
    except Exception:
        live_df = pd.DataFrame()

live_candidates = _decision_candidates(live_df)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">1. LIVE DECISION QUEUE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Primary gate: absolute price move ≥ ±0.75%. '
    'Then progress is measured against each stock\'s frozen Opening Straddle Premium: '
    '25% = 0.25×S, 50% = 0.50×S, 75% = 0.75×S, 100% = 1.00×S (factual breakout). '
    'Confirmation factors rank the candidates; they do not replace the primary gates.</div>',
    unsafe_allow_html=True,
)

if live_candidates.empty:
    st.info("No LIVE decision candidates at the latest source timestamp.")
else:
    q = _queue(live_candidates, "sdl_live_decision_filter")
    if q.empty:
        st.info("No LIVE candidates match the selected filter.")
    else:
        st.dataframe(q.style.apply(_decision_style, axis=1), width="stretch", hide_index=True)

st.markdown("</div>", unsafe_allow_html=True)

replay_events, replay_df, replay_ts = _replay_state()

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">2. INTRADAY / REPLAY DECISION QUEUE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Point-in-time queue. The frozen opening straddle is fixed. '
    'Progress bands use 0.25×S / 0.50×S / 0.75×S / 1.00×S, and only evidence available at '
    'the selected timestamp can affect confirmation and priority.</div>',
    unsafe_allow_html=True,
)

replay_candidates = _decision_candidates(replay_df)
if replay_candidates.empty or pd.isna(replay_ts):
    st.info("Replay an exact source snapshot above to populate this queue.")
else:
    st.caption(f"Replay boundary: **{replay_ts.strftime('%d %b %Y, %H:%M:%S')}**")
    q = _queue(replay_candidates, "sdl_replay_decision_filter")
    if q.empty:
        st.info("No replay candidates match the selected filter.")
    else:
        st.dataframe(q.style.apply(_decision_style, axis=1), width="stretch", hide_index=True)

st.markdown("</div>", unsafe_allow_html=True)


def _counts(df):
    if df.empty:
        return {"bull":0,"bear":0,"strong":0,"dev":0,"wait":0,"break":0}
    return {
        "bull": int((df["direction_label"]=="BULLISH").sum()),
        "bear": int((df["direction_label"]=="BEARISH").sum()),
        "strong": int((df["strength_label"]=="STRONG").sum()),
        "dev": int((df["strength_label"]=="DEVELOPING").sum()),
        "wait": int(df["strength_label"].isin(["WAIT","WAIT / CONFLICT"]).sum()),
        "break": int(df["factual_breakout"].sum()),
    }


lc = _counts(live_candidates)
rc = _counts(replay_candidates)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">3. DECISION STATE</div>', unsafe_allow_html=True)
cols = st.columns(8)
items = [
    ("LIVE CANDIDATES", len(live_candidates)),
    ("BULLISH", lc["bull"]),
    ("BEARISH", lc["bear"]),
    ("STRONG", lc["strong"]),
    ("DEVELOPING", lc["dev"]),
    ("WAIT", lc["wait"]),
    ("BREAKOUT", lc["break"]),
    ("LATEST", latest_ts.strftime("%H:%M:%S") if pd.notna(latest_ts) else "—"),
]
for col, (label, value) in zip(cols, items):
    with col:
        st.markdown(
            f'<div class="metric"><div class="metric-label">{label}</div>'
            f'<div class="metric-value" style="font-size:16px">{value}</div></div>',
            unsafe_allow_html=True,
        )
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">4. DECISION INSPECTOR</div>', unsafe_allow_html=True)
inspect_df = live_candidates if not live_candidates.empty else replay_candidates
if inspect_df.empty:
    st.info("No candidate available.")
else:
    options = inspect_df["symbol"].astype(str).tolist()
    selected = st.selectbox("Candidate", options, key="sdl_selected_candidate")
    row = inspect_df[inspect_df["symbol"].eq(selected)].iloc[0]

    css = "decision-up" if row["direction_label"]=="BULLISH" else "decision-down"
    if row["strength_label"] in {"WAIT","WAIT / CONFLICT"}:
        css = "decision-watch"

    st.markdown(
        f'<div class="card {css}" style="margin-top:0">'
        f'<div class="decision-main">{row["decision"]}</div>'
        f'<div class="decision-meta">Stage: {row["stage"]} · '
        f'Straddle progress: {row["progress"]:.1f}% of frozen S · '
        f'Price move: {row["signed_price_move_pct"]:+.2f}% · '
        f'Frozen straddle: ₹{row["frozen_straddle"]:.2f}</div></div>',
        unsafe_allow_html=True,
    )

    a,b,c,d,e = st.columns(5)
    a.metric("Open", f'{row["opening_price"]:.2f}')
    b.metric("Current", f'{row["current_price"]:.2f}')
    c.metric("Straddle ₹", f'{row["frozen_straddle"]:.2f}')
    d.metric("Upper Breakout", f'{row["upper_breakout"]:.2f}')
    e.metric("Lower Breakout", f'{row["lower_breakout"]:.2f}')

    st.caption(
        f'Progress levels from frozen S ₹{row["frozen_straddle"]:.2f}: '
        f'25% ₹{row["opening_price"] + row["frozen_straddle"] * 0.25:.2f} / '
        f'50% ₹{row["opening_price"] + row["frozen_straddle"] * 0.50:.2f} / '
        f'75% ₹{row["opening_price"] + row["frozen_straddle"] * 0.75:.2f} / '
        f'100% ₹{row["opening_price"] + row["frozen_straddle"]:.2f} UP; '
        f'DOWN levels are symmetric.'
    )

    factor_rows = []
    for f in row.get("factors", []):
        factor_rows.append({"FACTOR": f.label, "STATE": f.state, "WEIGHT": f.weight})
    st.dataframe(pd.DataFrame(factor_rows), width="stretch", hide_index=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">5. BREAKOUT INTELLIGENCE — ACTIVE TRADING DAY</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Factual first-breakout events detected for the active source trading day. '
    'Presentation only — this does not change the SDL selection or confirmation logic.</div>',
    unsafe_allow_html=True,
)

today_hist, archive_hist = _historical_intelligence(events, today_iso)

if today_hist.empty:
    st.info(
        f"No factual first-breakout event is currently recorded for {pd.Timestamp(today_iso).strftime('%d %b %Y')}. "
        "Run PROCESS LATEST or REPLAY DAY after the source snapshots are available."
    )
else:
    _render_breakout_table(today_hist, compact=True)

    with st.expander("Today's breakout evidence detail", expanded=False):
        _render_breakout_table(today_hist, compact=False)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">6. HISTORICAL BREAKOUT ARCHIVE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="card-subtitle">Previous factual first-breakout events. '
    'The archive is separate from the current live/replay decision queue.</div>',
    unsafe_allow_html=True,
)

if archive_hist.empty:
    st.info("No previous historical breakout events recorded.")
else:
    _render_breakout_table(archive_hist.head(250), compact=True)

    with st.expander("Historical raw evidence", expanded=False):
        cols = [
            "observation_timestamp","trading_date","symbol","direction",
            "open_price","current_price","opening_straddle_premium",
            "expected_1x_price","breakout_distance","price_chg_pct",
            "oi_chg_pct","ce_oi_chg_pct","pe_oi_chg_pct","pe_minus_ce_oi_chg",
            "iv_chg_pct","pcr_chg_pct"
        ]
        cols = [c for c in cols if c in archive_hist.columns]
        st.dataframe(archive_hist[cols].head(250), width="stretch", hide_index=True)

st.markdown(
    '<div style="margin-top:10px;color:#737c90;font-size:11px;">'
    'SDL boundary: source workbooks are read-only. No derivative-signal module is used. '
    'Decision filters are presentation-only; candidate selection is performed before the filters.'
    '</div>',
    unsafe_allow_html=True,
)
