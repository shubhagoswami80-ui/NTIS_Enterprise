from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config import INTRADAY_SOURCE_ROOT, STATE_JSON
from source_loader import discover_daywise_files, parse_observation_timestamp, read_source
from storage import load_state, save_state
from derivative_signal.signal_engine import build_signal
from decision_evidence import merge_evidence, enrich_decision

STATE_KEY = "derivative_signal"

QUALIFIED_STATES = {
    "STRONG_BULLISH", "STRONG_BEARISH", "STRONG_NEAR_LEVEL",
    "ACTIVE_BULLISH", "ACTIVE_BEARISH", "WAIT_BREAK_CONFIRMATION",
    "DEVELOPING", "DIRECTIONAL_UNCONFIRMED",
}


def _discover_sources(trading_date: str, source_root: Path | None = None) -> list[Path]:
    root = Path(source_root or INTRADAY_SOURCE_ROOT).expanduser()
    files = discover_daywise_files(root, trading_date)
    return sorted(
        [Path(p) for p in files if Path(p).is_file()],
        key=lambda p: (parse_observation_timestamp(p), p.stat().st_mtime, p.name.lower()),
    )


def _read(path: Path) -> pd.DataFrame:
    df = read_source(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _previous(state: dict[str, Any], trading_date: str) -> dict[str, dict]:
    return state.get(STATE_KEY, {}).get(trading_date, {}).get("previous_snapshot", {}) or {}


def _snapshot_rows(df: pd.DataFrame) -> dict[str, dict]:
    keep = [
        "Symbol", "symbol", "Close", "close", "Price Chg %", "price_chg_pct",
        "OI Chg %", "oi_chg_pct", "Tot PE-CE OI Chg", "pe_ce_oi_chg",
        "PCR Chg %", "pcr_chg_pct", "IV Chg %", "iv_chg_pct",
        "Volume Chg %", "volume_chg_pct", "ATM Straddle %", "atm_straddle_pct",
        "Support", "support", "Resistance", "resistance",
        "Futures Buildup", "fut_buildup", "Futures OI Chg %", "fut_oi_chg_pct",
    ]
    rows: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        symbol = str(record.get("Symbol", record.get("symbol", ""))).strip().upper()
        if symbol:
            rows[symbol] = {k: record.get(k) for k in keep if k in record}
    return rows


def _process_snapshot(path: Path, trading_date: str, previous: dict[str, dict]) -> pd.DataFrame:
    # The selected path is the authoritative BASE snapshot for this iteration.
    df, source_map = merge_evidence(path, trading_date)
    rows: list[dict[str, Any]] = []

    for record in df.to_dict(orient="records"):
        symbol = str(record.get("symbol", record.get("Symbol", ""))).strip().upper()
        if not symbol:
            continue

        signal = build_signal(record, previous.get(symbol))
        signal["source_evidence"] = source_map
        # Evidence must inspect CURRENT merged data, never the previous snapshot.
        signal = enrich_decision(signal, record)
        rows.append(signal)

    return pd.DataFrame(rows)


def process_selected_source(path: Path, trading_date: str) -> pd.DataFrame:
    state = load_state(STATE_JSON)
    previous = _previous(state, trading_date)
    result = _process_snapshot(path, trading_date, previous)

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    day["previous_snapshot"] = _snapshot_rows(_read(path))
    day["source_file"] = str(path)
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)
    return result


def process_all_sources(paths: list[Path], trading_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    state = load_state(STATE_JSON)
    previous: dict[str, dict] = {}
    previous_state: dict[str, str] = {}
    timeline_rows: list[dict[str, Any]] = []
    latest_result = pd.DataFrame()

    ordered = sorted(
        [Path(p) for p in paths if Path(p).is_file()],
        key=lambda p: (parse_observation_timestamp(p), p.stat().st_mtime, p.name.lower()),
    )

    for sequence, path in enumerate(ordered, start=1):
        result = _process_snapshot(path, trading_date, previous)
        if result.empty:
            continue

        timestamp = parse_observation_timestamp(path)

        for row in result.to_dict(orient="records"):
            symbol = str(row.get("symbol", "")).upper()
            state_name = str(row.get("state", "WATCH"))
            old_state = previous_state.get(symbol)

            if state_name != old_state and state_name in QUALIFIED_STATES:
                timeline_rows.append({
                    "Time": timestamp.strftime("%H:%M:%S"),
                    "Snapshot": sequence,
                    "Symbol": symbol,
                    "Direction": row.get("direction", "NEUTRAL"),
                    "Setup": row.get("setup", row.get("opportunity", "WATCH")),
                    "State": state_name,
                    "S/R": row.get("sr_status", row.get("location", "UNKNOWN")),
                    "Action": row.get("action", "WATCH"),
                    "Evidence": row.get("decision_quality", "LOW"),
                })
            previous_state[symbol] = state_name

        previous = _snapshot_rows(_read(path))
        latest_result = result

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    day["previous_snapshot"] = previous
    day["source_file"] = str(ordered[-1]) if ordered else ""
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)

    return latest_result, pd.DataFrame(timeline_rows)


def _num(v):
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _rank(result: pd.DataFrame) -> pd.DataFrame:
    if result.empty:
        return result.copy()

    out = result.copy()
    rank_map = {
        "CONFIRMED": 8, "BREAKOUT": 8, "BREAKDOWN": 8,
        "REVERSAL_CONFIRMED": 8, "DEVELOPING": 5,
        "WAIT": 4, "CONFLICT": 2, "WATCH": 1,
    }
    out["_action_rank"] = out["action"].map(rank_map).fillna(0)
    out["_quality_rank"] = out["decision_quality"].map({"HIGH": 3, "MEDIUM": 2, "LOW": 1}).fillna(0)
    out["_sr_rank"] = out["sr_status"].astype(str).str.contains(
        "BROKEN|CROSSED|REVERSAL|CONFIR", case=False, regex=True
    ).astype(int)
    out["_score"] = (
        out["_action_rank"] * 10
        + out["_quality_rank"] * 3
        + out["_sr_rank"] * 2
        + pd.to_numeric(out.get("confluence_score", 0), errors="coerce").fillna(0)
    )
    return out.sort_values(["_score", "strength"], ascending=False, na_position="last")


def _css():
    st.markdown("""
<style>
.block-container {max-width:1450px;padding-top:1.5rem}
.hero {padding:22px 26px;border-radius:16px;background:#172554;color:white;margin-bottom:16px}
.hero-title {font-size:29px;font-weight:800}.hero-sub {font-size:13px;opacity:.82;margin-top:4px}
.card {border:1px solid #e2e8f0;border-radius:14px;padding:15px;background:#fff;min-height:205px;box-shadow:0 2px 8px rgba(15,23,42,.06)}
.bull {color:#15803d;font-weight:800}.bear {color:#dc2626;font-weight:800}.wait {color:#a16207;font-weight:800}
.small {font-size:12px;color:#64748b}.metric {font-size:20px;font-weight:800;color:#0f172a}
.action {padding:9px 11px;border-radius:9px;background:#eef2ff;color:#312e81;font-weight:800;margin-top:8px}
.sr {padding:8px 10px;border-radius:8px;background:#f8fafc;margin-top:7px;font-size:12px}
</style>
""", unsafe_allow_html=True)


def _direction_html(direction: str) -> str:
    d = str(direction).upper()
    if d == "BULLISH":
        return '<span class="bull">BULLISH</span>'
    if d == "BEARISH":
        return '<span class="bear">BEARISH</span>'
    return '<span class="wait">NEUTRAL</span>'


def _render_cards(result: pd.DataFrame):
    ranked = _rank(result)
    if ranked.empty:
        st.info("No decision candidates available.")
        return

    st.subheader("Top Tradable Decisions")

    for start in range(0, min(len(ranked), 8), 4):
        cols = st.columns(4)
        for col, (_, r) in zip(cols, ranked.iloc[start:start + 4].iterrows()):
            with col:
                direction = str(r.get("direction", "NEUTRAL"))
                action = str(r.get("action", "WATCH"))
                setup = str(r.get("setup", r.get("opportunity", "WATCH")))
                sr_status = str(r.get("sr_status", r.get("location", "UNKNOWN")))
                cmpv = _num(r.get("reference_price"))
                support = _num(r.get("support"))
                resistance = _num(r.get("resistance"))

                st.markdown(f"""
<div class="card">
  <div class="metric">{r.get('symbol','')}</div>
  <div>{_direction_html(direction)} &nbsp; | &nbsp; {setup}</div>
  <div class="small">Decision confidence: {r.get('decision_quality','LOW')} &nbsp; | &nbsp; Strength {r.get('strength',0)}/5</div>
  <div class="sr"><b>S/R:</b> {sr_status}<br>
  CMP: {('—' if cmpv is None else f'{cmpv:.2f}')} &nbsp;
  Support: {('—' if support is None else f'{support:.2f}')} &nbsp;
  Resistance: {('—' if resistance is None else f'{resistance:.2f}')}</div>
  <div class="small" style="margin-top:7px"><b>Why:</b> {r.get('decision_reason','Evidence being compiled')}</div>
  <div class="action">{action}</div>
</div>
""", unsafe_allow_html=True)


def _render_decision_table(result: pd.DataFrame):
    ranked = _rank(result)
    if ranked.empty:
        return

    st.subheader("Decision Table")
    table = pd.DataFrame({
        "Rank": range(1, len(ranked) + 1),
        "Stock": ranked["symbol"].astype(str),
        "Direction": ranked["direction"].astype(str),
        "Setup": ranked.get("setup", ranked.get("opportunity", "WATCH")).astype(str),
        "S/R": ranked.get("sr_status", ranked.get("location", "UNKNOWN")).astype(str),
        "Confirmation": ranked.get("confirmation", ranked.get("decision_quality", "LOW")).astype(str),
        "Action": ranked["action"].astype(str),
        "Why": ranked.get("decision_reason", "").astype(str),
    }).head(20)

    st.dataframe(table, use_container_width=True, hide_index=True)


def _render_evidence(row: pd.Series):
    st.subheader(f"Decision Evidence - {row['symbol']}")
    cols = st.columns(4)
    metrics = [
        ("CMP", row.get("reference_price")),
        ("Support", row.get("support")),
        ("Resistance", row.get("resistance")),
        ("S/R Distance %", row.get("sr_distance_pct")),
    ]
    for col, (label, value) in zip(cols, metrics):
        with col:
            v = _num(value)
            st.metric(label, "—" if v is None else f"{v:.2f}")

    evidence = pd.DataFrame({
        "Evidence": [
            "Price / Direction", "Futures", "PE-CE OI", "PCR",
            "IV", "Volume", "Momentum", "S/R", "Straddle",
        ],
        "Interpretation": [
            row.get("directional_interpretation", "—"),
            row.get("futures_interpretation", "—"),
            row.get("options_interpretation", "—"),
            row.get("pcr_interpretation", "—"),
            row.get("iv_interpretation", "—"),
            row.get("volume_interpretation", "—"),
            row.get("momentum_state", "—"),
            row.get("sr_interpretation", "—"),
            row.get("straddle_interpretation", "—"),
        ],
    })
    st.dataframe(evidence, use_container_width=True, hide_index=True)

    st.markdown(
        f'<div class="action"><b>Decision:</b> {row.get("decision_reason","—")} '
        f'&nbsp; <b>Action:</b> {row.get("action","WATCH")}</div>',
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="NTIS SDL - Intraday Decision Center", layout="wide")
    _css()

    st.markdown("""
<div class="hero">
  <div class="hero-title">NTIS SDL - Intraday Decision Center</div>
  <div class="hero-sub">Decision-oriented intraday analysis. Evidence is compiled into ranked setups.</div>
</div>
""", unsafe_allow_html=True)

    default_root = str(Path(INTRADAY_SOURCE_ROOT).expanduser())
    source_text = st.text_input("Source folder", value=default_root, help="Select the folder containing the Daywise snapshots and supporting evidence files.")
    source_root = Path(source_text).expanduser()

    c1, c2, c3 = st.columns([1, 1, 1.5])
    with c1:
        trading_date = st.date_input("Trading date", value=date.today()).strftime("%Y-%m-%d")
    with c2:
        mode = st.radio("Read mode", ["Latest File", "All Files / Day Replay"], horizontal=False)
    with c3:
        st.caption(f"Source: {source_root}")

    try:
        sources = _discover_sources(trading_date, source_root)
    except Exception as exc:
        st.error(f"Source discovery failed: {type(exc).__name__}: {exc}")
        return

    if not sources:
        st.warning("No Daywise snapshots found for the selected date in the selected folder.")
        return

    labels = [
        f"{parse_observation_timestamp(p):%H:%M:%S} - {p.name}"
        for p in sources
    ]

    if mode == "Latest File":
        selected_idx = st.selectbox("Snapshot", list(range(len(sources))), index=len(sources) - 1, format_func=lambda i: labels[i])
        if st.button("PROCESS SELECTED SNAPSHOT", type="primary", use_container_width=True):
            st.session_state["ds_result"] = process_selected_source(sources[selected_idx], trading_date)
            st.session_state["ds_timeline"] = pd.DataFrame()
            st.session_state["ds_mode"] = mode
    else:
        st.info(f"{len(sources)} snapshots discovered. Replay will process them chronologically.")
        if st.button("PROCESS ALL FILES / DAY REPLAY", type="primary", use_container_width=True):
            latest, timeline = process_all_sources(sources, trading_date)
            st.session_state["ds_result"] = latest
            st.session_state["ds_timeline"] = timeline
            st.session_state["ds_mode"] = mode

    result = st.session_state.get("ds_result")
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        st.info("Select a mode and process the data.")
        return

    result = result.copy()
    st.success(f"{len(result)} symbols evaluated using compiled decision evidence.")

    _render_cards(result)
    _render_decision_table(result)

    ranked = _rank(result)
    if not ranked.empty:
        symbol = st.selectbox("Inspect one decision", ranked["symbol"].tolist())
        row = ranked.loc[ranked["symbol"] == symbol].iloc[0]
        _render_evidence(row)

    timeline = st.session_state.get("ds_timeline")
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        st.subheader("Decision Changes During Day Replay")
        st.dataframe(timeline, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()


def render():
    main()

