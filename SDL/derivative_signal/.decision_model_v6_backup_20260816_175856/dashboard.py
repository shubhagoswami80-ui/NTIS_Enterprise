from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config import INTRADAY_SOURCE_ROOT
STATE_JSON = Path(__file__).resolve().parent / 'data' / 'output' / 'state' / 'processing_state.json'
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
        "Symbol", "symbol", "Open", "open", "High", "high", "Low", "low",
        "Close", "close", "Price Chg %", "price_chg_pct",
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



def _first_range_from_path(path: Path, trading_date: str) -> dict[str, dict[str, Any]]:
    try:
        files = _discover_sources(trading_date, path.parent)
        if not files:
            return {}
        first = files[0]
        df = _read(first)
        symbol_col = next((c for c in ("Symbol", "symbol") if c in df.columns), None)
        high_col = next((c for c in ("High", "high") if c in df.columns), None)
        low_col = next((c for c in ("Low", "low") if c in df.columns), None)
        if not symbol_col or not high_col or not low_col:
            return {}
        result = {}
        for rec in df.to_dict(orient="records"):
            symbol = str(rec.get(symbol_col, "")).strip().upper()
            if not symbol:
                continue
            try:
                high = float(rec.get(high_col))
                low = float(rec.get(low_col))
            except (TypeError, ValueError):
                continue
            if pd.isna(high) or pd.isna(low):
                continue
            result[symbol] = {
                "first_snapshot_high": high,
                "first_snapshot_low": low,
                "first_snapshot_path": str(first),
                "first_snapshot_timestamp": parse_observation_timestamp(first),
            }
        return result
    except Exception:
        return {}

def _process_snapshot(path: Path, trading_date: str, previous: dict[str, dict], first_range: dict[str, Any] | None = None) -> pd.DataFrame:
    df, source_map = merge_evidence(path, trading_date)
    first_range = first_range or {}
    rows = []

    for record in df.to_dict(orient="records"):
        symbol = str(record.get("symbol", record.get("Symbol", ""))).strip().upper()
        if not symbol:
            continue

        signal = build_signal(record, previous.get(symbol))
        signal["source_evidence"] = source_map
        enriched = enrich_decision(signal, record, context=first_range)
        rows.append(enriched)

    return pd.DataFrame(rows)


def process_selected_source(path: Path, trading_date: str) -> pd.DataFrame:
    state = load_state(STATE_JSON)
    previous = _previous(state, trading_date)
    first_range = _first_range_from_path(path, trading_date)
    result = _process_snapshot(path, trading_date, previous, first_range)

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

    ordered = sorted([Path(p) for p in paths if Path(p).is_file()],
                     key=lambda p: (parse_observation_timestamp(p), p.stat().st_mtime, p.name.lower()))
    first_range = _first_range_from_path(ordered[0], trading_date) if ordered else {}

    for sequence, path in enumerate(ordered, start=1):
        result = _process_snapshot(path, trading_date, previous, first_range)
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
                    "First Range": row.get("first_range_status", "UNAVAILABLE"),
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


# Preserve the frozen UI below this point by importing and delegating to the
# existing card/table rendering helpers from the current frozen dashboard.
# This compact wrapper is intentionally UI-neutral.

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
    price = pd.to_numeric(
        out.get("price_change_pct", pd.Series(0, index=out.index)),
        errors="coerce",
    )
    direction = out.get(
        "direction", pd.Series("NEUTRAL", index=out.index)
    ).astype(str).str.upper()

    # HARD ELIGIBILITY: agreed +/-0.75% rule.
    eligible = (
        ((direction == "BULLISH") & (price > 0.75))
        | ((direction == "BEARISH") & (price < -0.75))
    )
    out = out.loc[eligible].copy()
    if out.empty:
        return out

    def num(name):
        return pd.to_numeric(
            out.get(name, pd.Series(0, index=out.index)),
            errors="coerce"
        ).fillna(0)

    state_rank = out.get("state", pd.Series("", index=out.index)).astype(str).map({
        "STRONG_BULLISH": 50,
        "STRONG_BEARISH": 50,
        "STRONG_NEAR_LEVEL": 44,
        "ACTIVE_BULLISH": 38,
        "ACTIVE_BEARISH": 38,
        "WAIT_BREAK_CONFIRMATION": 28,
        "DEVELOPING": 22,
        "DIRECTIONAL_UNCONFIRMED": 10,
    }).fillna(0)

    confirmation_rank = out.get(
        "confirmation", pd.Series("", index=out.index)
    ).astype(str).map({
        "CONFIRMED": 30,
        "DEVELOPING": 16,
        "BREAKOUT vs REJECTION": 8,
        "BOUNCE vs BREAKDOWN": 8,
    }).fillna(0)

    quality_rank = out.get(
        "decision_quality", pd.Series("", index=out.index)
    ).astype(str).map({
        "HIGH": 15,
        "MEDIUM": 8,
        "LOW": 2,
    }).fillna(0)

    range_rank = out.get(
        "first_range_status", pd.Series("", index=out.index)
    ).astype(str).map({
        "FIRST-HIGH BROKEN": 20,
        "FIRST-LOW BROKEN": 20,
        "TESTING FIRST-HIGH": 8,
        "TESTING FIRST-LOW": 8,
    }).fillna(0)

    out["_decision_priority"] = (
        state_rank
        + confirmation_rank
        + quality_rank
        + range_rank
        + num("confluence_score") * 5
        + num("strength") * 4
        + num("momentum_score") * 2
        + (price.abs() - 0.75).clip(lower=0) * 2
        - num("conflict_count") * 8
    )
    out["_price_abs"] = price.abs()

    return out.sort_values(
        ["_decision_priority", "_price_abs", "symbol"],
        ascending=[False, False, True],
        na_position="last",
    )


def _fmt(v, suffix=""):
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return "—"
        return f"{float(v):.2f}{suffix}"
    except (TypeError, ValueError):
        return "—"


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
                setup = str(r.get("setup", r.get("opportunity", "WATCH")))
                sr = str(r.get("sr_status", "UNKNOWN"))
                first_range = str(r.get("first_range_status", "UNAVAILABLE"))
                action = str(r.get("action", "WATCH"))
                cmpv = _num(r.get("reference_price"))
                support = _num(r.get("support"))
                resistance = _num(r.get("resistance"))
                st.markdown(f"""
<div class="card">
  <div class="metric">{r.get('symbol','')}</div>
  <div>{_direction_html(direction)} &nbsp; | &nbsp; {setup}</div>
  <div class="small">Confidence {r.get('decision_quality','LOW')} | Strength {r.get('strength',0)}/5</div>
  <div class="sr"><b>S/R:</b> {sr}<br>
  <b>First Range:</b> {first_range}<br>
  CMP: {('—' if cmpv is None else f'{cmpv:.2f}')} &nbsp;
  S: {('—' if support is None else f'{support:.2f}')} &nbsp;
  R: {('—' if resistance is None else f'{resistance:.2f}')}</div>
  <div class="small" style="margin-top:7px"><b>Why:</b> {r.get('decision_reason','—')}</div>
  <div class="action">{action}</div>
</div>
""", unsafe_allow_html=True)


def _render_decision_table(result: pd.DataFrame):
    ranked = _rank(result)
    if ranked.empty:
        return
    st.subheader("Decision Table")
    st.dataframe(pd.DataFrame({
        "Rank": range(1, len(ranked)+1),
        "Stock": ranked["symbol"].astype(str),
        "Direction": ranked["direction"].astype(str),
        "Setup": ranked["setup"].astype(str),
        "S/R": ranked["sr_status"].astype(str),
        "First Range": ranked["first_range_status"].astype(str),
        "Confirmation": ranked["confirmation"].astype(str),
        "Action": ranked["action"].astype(str),
        "Why": ranked["decision_reason"].astype(str),
    }).head(20), use_container_width=True, hide_index=True)


def _render_evidence(row: pd.Series):
    st.subheader(f"Decision Evidence - {row['symbol']}")
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [
        ("CMP", row.get("reference_price")),
        ("Support", row.get("support")),
        ("Resistance", row.get("resistance")),
        ("First High", row.get("first_snapshot_high")),
    ]):
        with col:
            v = _num(value)
            st.metric(label, "—" if v is None else f"{v:.2f}")
    st.caption(
        f"First Low: {_fmt(row.get('first_snapshot_low'))} | "
        f"S/R: {row.get('sr_status','—')} | "
        f"Setup: {row.get('setup','—')} | Action: {row.get('action','—')}"
    )
    evidence = pd.DataFrame({
        "Evidence": [
            "Price / Direction","First Range","Futures","PE-CE OI","PCR","IV",
            "Volume","Momentum","S/R","Straddle"
        ],
        "Interpretation": [
            row.get("directional_interpretation","—"),
            row.get("first_range_status","—"),
            row.get("futures_interpretation","—"),
            row.get("options_interpretation","—"),
            row.get("pcr_interpretation","—"),
            row.get("iv_interpretation","—"),
            row.get("volume_interpretation","—"),
            row.get("momentum_state","—"),
            row.get("sr_interpretation","—"),
            row.get("straddle_interpretation","—"),
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

    source_text = st.text_input("Source folder", value=str(Path(INTRADAY_SOURCE_ROOT).expanduser()))
    source_root = Path(source_text).expanduser()

    c1, c2, c3 = st.columns([1,1,1.5])
    with c1:
        trading_date = st.date_input("Trading date", value=date.today()).strftime("%Y-%m-%d")
    with c2:
        mode = st.radio("Read mode", ["Latest File","All Files / Day Replay"])
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

    if mode == "Latest File":
        idx = st.selectbox(
            "Snapshot",
            list(range(len(sources))),
            index=len(sources)-1,
            format_func=lambda i: f"{parse_observation_timestamp(sources[i]):%H:%M:%S} - {sources[i].name}",
        )
        if st.button("PROCESS SELECTED SNAPSHOT", type="primary", use_container_width=True):
            st.session_state["ds_result"] = process_selected_source(sources[idx], trading_date)
            st.session_state["ds_timeline"] = pd.DataFrame()
    else:
        st.info(f"{len(sources)} snapshots discovered. Replay will process them chronologically.")
        if st.button("PROCESS ALL FILES / DAY REPLAY", type="primary", use_container_width=True):
            try:
                latest, timeline = process_all_sources(sources, trading_date)
                st.session_state["ds_result"] = latest
                st.session_state["ds_timeline"] = timeline
            except Exception as exc:
                st.error(f"Replay failed: {type(exc).__name__}: {exc}")

    result = st.session_state.get("ds_result")
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        st.info("Select a mode and process the data.")
        return

    st.success(f"{len(result)} symbols evaluated using compiled decision evidence.")
    _render_cards(result)
    _render_decision_table(result)

    ranked = _rank(result)
    if not ranked.empty:
        symbol = st.selectbox("Inspect one decision", ranked["symbol"].tolist())
        _render_evidence(ranked.loc[ranked["symbol"] == symbol].iloc[0])

    timeline = st.session_state.get("ds_timeline")
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        st.subheader("Decision Changes During Day Replay")
        st.dataframe(timeline, use_container_width=True, hide_index=True)


def render():
    main()
