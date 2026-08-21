from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config import INTRADAY_SOURCE_ROOT
STATE_JSON = Path(__file__).resolve().parent / "data" / "output" / "state" / "processing_state.json"
from source_loader import discover_daywise_files, parse_observation_timestamp, read_source
from storage import load_state, save_state
from derivative_signal.signal_engine import build_signal
from decision_evidence import merge_evidence, enrich_decision

STATE_KEY = "derivative_signal"
CONFIRMED_STATES = {
    "STRONG_BULLISH", "STRONG_BEARISH", "STRONG_NEAR_LEVEL",
    "ACTIVE_BULLISH", "ACTIVE_BEARISH", "WAIT_BREAK_CONFIRMATION",
}
DEVELOPING_STATES = {"DEVELOPING_BULLISH", "DEVELOPING_BEARISH"}
QUALIFIED_STATES = CONFIRMED_STATES | DEVELOPING_STATES


def _discover_sources(trading_date: str, source_root: Path | None = None) -> list[Path]:
    root = Path(source_root or INTRADAY_SOURCE_ROOT).expanduser()
    files = discover_daywise_files(root, trading_date)
    return sorted([Path(p) for p in files if Path(p).is_file()],
                  key=lambda p: (parse_observation_timestamp(p), p.stat().st_mtime, p.name.lower()))


def _read(path: Path) -> pd.DataFrame:
    df = read_source(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _previous(state: dict[str, Any], trading_date: str) -> dict[str, dict]:
    return state.get(STATE_KEY, {}).get(trading_date, {}).get("previous_snapshot", {}) or {}


def _snapshot_rows(df: pd.DataFrame) -> dict[str, dict]:
    keep = [
        "Symbol", "symbol", "Open", "open", "High", "high", "Low", "low",
        "Close", "close", "Price Chg %", "price_chg_pct", "OI Chg %", "oi_chg_pct",
        "Tot PE-CE OI Chg", "pe_ce_oi_chg", "PCR Chg %", "pcr_chg_pct", "IV Chg %", "iv_chg_pct",
        "Volume Chg %", "volume_chg_pct", "ATM Straddle %", "atm_straddle_pct",
        "Support", "support", "Resistance", "resistance", "Futures Buildup", "fut_buildup",
        "Futures OI Chg %", "fut_oi_chg_pct",
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
        result: dict[str, dict[str, Any]] = {}
        for rec in df.to_dict(orient="records"):
            symbol = str(rec.get(symbol_col, "")).strip().upper()
            if not symbol:
                continue
            try:
                high, low = float(rec.get(high_col)), float(rec.get(low_col))
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
    rows = []
    for record in df.to_dict(orient="records"):
        symbol = str(record.get("symbol", record.get("Symbol", ""))).strip().upper()
        if not symbol:
            continue
        signal = build_signal(record, previous.get(symbol))
        signal["source_evidence"] = source_map
        rows.append(enrich_decision(signal, record, context=first_range or {}))
    return pd.DataFrame(rows)


def process_selected_source(path: Path, trading_date: str) -> pd.DataFrame:
    state = load_state(STATE_JSON)
    result = _process_snapshot(path, trading_date, _previous(state, trading_date), _first_range_from_path(path, trading_date))
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
            state_name = str(row.get("decision_state", row.get("state", "WATCH")))
            old_state = previous_state.get(symbol)
            if state_name != old_state and state_name in QUALIFIED_STATES:
                timeline_rows.append({
                    "Time": timestamp.strftime("%H:%M:%S"), "Snapshot": sequence, "Symbol": symbol,
                    "Decision": row.get("decision_state", "NO DECISION"),
                    "Evidence": row.get("decision_score", 0), "Strength": row.get("decision_strength", "—"),
                    "S/R": row.get("sr_status", "—"),
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


def _sr_bucket(row: pd.Series) -> tuple[str, str]:
    d = str(row.get("decision_direction", row.get("direction", "NEUTRAL"))).upper()
    raw = str(row.get("sr_status", "")).upper().strip()
    if raw:
        return raw, d
    # Compatibility fallback if older decision_evidence did not populate sr_status.
    if d == "BULLISH":
        if raw == "RESISTANCE BROKEN":
            return raw, d
    if d == "BEARISH":
        if raw == "SUPPORT BROKEN":
            return raw, d
    return "S/R STATUS UNAVAILABLE", d


def _phase(row: pd.Series) -> str:
    state = str(row.get("decision_state", "")).upper()
    if state.startswith("DEVELOPING"):
        return "DEVELOPING"
    if state in {"STRONG_BULLISH", "ACTIVE_BULLISH", "STRONG_BEARISH", "ACTIVE_BEARISH"}:
        return "CONFIRMED"
    if state == "STRONG_NEAR_LEVEL":
        return "NEAR LEVEL"
    if state == "WAIT_BREAK_CONFIRMATION":
        return "WAIT BREAK"
    return state or "NO DECISION"


def _rank(result: pd.DataFrame) -> pd.DataFrame:
    if result.empty:
        return result.copy()
    out = result.copy()
    decision = out.get("decision_direction", out.get("direction", pd.Series("NEUTRAL", index=out.index))).astype(str).str.upper()
    price = pd.to_numeric(out.get("price_change_pct", pd.Series(0, index=out.index)), errors="coerce")
    state = out.get("decision_state", pd.Series("", index=out.index)).astype(str).str.upper()
    score = pd.to_numeric(out.get("decision_score", pd.Series(0, index=out.index)), errors="coerce").fillna(0)

    confirmed = (((decision == "BULLISH") & (price > 0.75)) | ((decision == "BEARISH") & (price < -0.75)))
    # IMPORTANT: dashboard visibility must not discard developing decisions simply because
    # they have not yet crossed the hard +/-0.75% confirmation gate.
    developing = state.isin(DEVELOPING_STATES)
    near_level = state.isin({"STRONG_NEAR_LEVEL", "WAIT_BREAK_CONFIRMATION"})
    out = out.loc[confirmed | developing | near_level].copy()
    if out.empty:
        return out

    def num(name):
        return pd.to_numeric(out.get(name, pd.Series(0, index=out.index)), errors="coerce").fillna(0)

    # S/R is a decision priority, not merely a display field.
    sr = out.get("sr_status", pd.Series("", index=out.index)).astype(str).str.upper()
    sr_rank = sr.map({
        "RESISTANCE BROKEN": 40, "SUPPORT BROKEN": 40,
        "RESISTANCE TEST": 30, "SUPPORT TEST": 30,
        "APPROACHING RESISTANCE": 25, "APPROACHING SUPPORT": 25,
        "AT_RESISTANCE": 28, "AT_SUPPORT": 28,
        "ROOM_TO_RESISTANCE": 16, "ROOM_TO_SUPPORT": 16,
    }).fillna(0)
    state_rank = state.map({
        "STRONG_BULLISH": 45, "STRONG_BEARISH": 45,
        "ACTIVE_BULLISH": 40, "ACTIVE_BEARISH": 40,
        "STRONG_NEAR_LEVEL": 35, "WAIT_BREAK_CONFIRMATION": 32,
        "DEVELOPING_BULLISH": 30, "DEVELOPING_BEARISH": 30,
    }).fillna(0)
    quality_rank = out.get("decision_quality", pd.Series("", index=out.index)).astype(str).map({"HIGH": 18, "MEDIUM": 10, "LOW": 4}).fillna(0)
    out["_decision_priority"] = (
        state_rank + sr_rank + quality_rank + num("decision_score") * 0.45
        + num("confluence_score") * 3 + num("strength") * 3 + num("momentum_score") * 2
        - num("conflict_count") * 8 + (price.abs() - 0.75).clip(lower=0) * 2
    )
    out["_price_abs"] = price.abs()
    return out.sort_values(["_decision_priority", "_price_abs", "symbol"], ascending=[False, False, True], na_position="last")


def _css():
    st.markdown("""
<style>
.block-container{max-width:1500px;padding-top:1.2rem}
.hero{padding:22px 26px;border-radius:16px;background:#172554;color:white;margin-bottom:16px}
.hero-title{font-size:29px;font-weight:800}.hero-sub{font-size:13px;opacity:.84;margin-top:4px}
.card{border:1px solid #e2e8f0;border-radius:14px;padding:15px;background:#fff;min-height:210px;box-shadow:0 2px 8px rgba(15,23,42,.06)}
.card-bull{border-left:6px solid #16a34a}.card-bear{border-left:6px solid #dc2626}.card-dev{border-left:6px solid #f59e0b}
.bull{color:#15803d;font-weight:900}.bear{color:#dc2626;font-weight:900}.develop{color:#b45309;font-weight:900}
.sr-cross{color:#166534;background:#dcfce7;font-weight:900}.sr-near{color:#92400e;background:#fef3c7;font-weight:900}.sr-broken{color:#991b1b;background:#fee2e2;font-weight:900}
.sr-chip{display:inline-block;padding:5px 8px;border-radius:7px;font-size:11px;margin-top:7px}
.small{font-size:12px;color:#64748b}.metric{font-size:20px;font-weight:800;color:#0f172a}
.score{font-size:18px;font-weight:900}.decision{padding:8px 10px;border-radius:9px;background:#eef2ff;color:#312e81;font-weight:800;margin-top:8px}
.sr{padding:8px 10px;border-radius:8px;background:#f8fafc;margin-top:7px;font-size:12px}
.pool{padding:9px 12px;border-radius:9px;background:#f8fafc;font-size:12px;margin-bottom:12px}
.section-bull{color:#15803d;font-weight:900}.section-bear{color:#dc2626;font-weight:900}
</style>""", unsafe_allow_html=True)


def _decision_html(row: pd.Series) -> str:
    d = str(row.get("decision_state", "")).upper()
    cls = "bull" if "BULLISH" in d else "bear" if "BEARISH" in d else "develop"
    return f'<span class="{cls}">{d or "NO DECISION"}</span>'


def _sr_html(row: pd.Series) -> str:
    sr, direction = _sr_bucket(row)
    if "BROKEN" in sr or "CROSSED" in sr:
        cls = "sr-cross" if direction == "BULLISH" else "sr-broken"
    elif "APPROACH" in sr or "TEST" in sr or "AT_" in sr:
        cls = "sr-near"
    else:
        cls = "sr-chip"
    return f'<span class="sr-chip {cls}">{sr.replace("_", " ")}</span>'


def _card_class(row: pd.Series) -> str:
    state = str(row.get("decision_state", "")).upper()
    if "BULLISH" in state:
        return "card-bull"
    if "BEARISH" in state:
        return "card-bear"
    return "card-dev"


def _render_card_rows(ranked: pd.DataFrame):
    for start in range(0, len(ranked), 4):
        cols = st.columns(4)
        for col, (_, r) in zip(cols, ranked.iloc[start:start + 4].iterrows()):
            with col:
                cmpv, support, resistance = map(_num, [r.get("reference_price"), r.get("support"), r.get("resistance")])
                score = _num(r.get("decision_score")); price = _num(r.get("price_change_pct"))
                score_text = f"{score:.0f}/100" if score is not None else "—"
                price_text = "—" if price is None else f"{price:+.2f}%"
                st.markdown(f"""
<div class="card {_card_class(r)}">
  <div class="metric">{r.get('symbol','')}</div>
  <div>{_decision_html(r)}</div>
  {_sr_html(r)}
  <div style="margin-top:8px"><span class="score">{score_text}</span> <span class="small">{r.get('decision_strength','—')}</span></div>
  <div class="small">Phase: <b>{_phase(r)}</b> &nbsp;|&nbsp; Quality {r.get('decision_quality','LOW')} &nbsp;|&nbsp; Confluence {r.get('confluence_score',0)}</div>
  <div class="sr">CMP: {('—' if cmpv is None else f'{cmpv:.2f}')} &nbsp; {price_text}<br>S: {('—' if support is None else f'{support:.2f}')} &nbsp; R: {('—' if resistance is None else f'{resistance:.2f}')}</div>
  <div class="decision">{r.get('decision_reason','—')}</div>
</div>""", unsafe_allow_html=True)


def _render_cards(result: pd.DataFrame):
    ranked = _rank(result)
    if ranked.empty:
        st.info("No decision candidates available.")
        return
    decision_direction = ranked.get("decision_direction", ranked.get("direction", pd.Series("NEUTRAL", index=ranked.index))).astype(str).str.upper()
    bullish = ranked.loc[decision_direction == "BULLISH"].head(8)
    bearish = ranked.loc[decision_direction == "BEARISH"].head(8)
    developing_count = int(ranked["decision_state"].astype(str).str.startswith("DEVELOPING").sum())
    confirmed_count = len(ranked) - developing_count
    st.markdown(f'<div class="pool"><b>Decision pool:</b> <span class="section-bull">Bullish {len(bullish)}</span> | <span class="section-bear">Bearish {len(bearish)}</span> | Confirmed/near-level {confirmed_count} | Developing {developing_count}</div>', unsafe_allow_html=True)
    st.subheader("Top Bullish Decisions")
    _render_card_rows(bullish) if not bullish.empty else st.info("No bullish decision candidate.")
    st.subheader("Top Bearish Decisions")
    _render_card_rows(bearish) if not bearish.empty else st.info("No bearish decision candidate.")


def _table_style(df: pd.DataFrame):
    def decision_color(v):
        s = str(v).upper()
        if "BULLISH" in s: return "color:#15803d;font-weight:800"
        if "BEARISH" in s: return "color:#dc2626;font-weight:800"
        return "color:#b45309;font-weight:800"
    def sr_color(v):
        s = str(v).upper()
        if "BROKEN" in s or "CROSSED" in s: return "color:#166534;background:#dcfce7;font-weight:900"
        if "APPROACH" in s or "TEST" in s or "AT " in s: return "color:#92400e;background:#fef3c7;font-weight:800"
        return ""
    return df.style.map(decision_color, subset=["Direction", "Phase"]).map(sr_color, subset=["S/R Decision"])


def _render_decision_table(result: pd.DataFrame):
    ranked = _rank(result)
    if ranked.empty:
        return
    st.subheader("Decision Table — ranked by strength, direction and S/R state")
    table = pd.DataFrame({
        "Rank": range(1, len(ranked) + 1),
        "Stock": ranked["symbol"].astype(str),
        "Direction": ranked.get("decision_direction", pd.Series("NEUTRAL", index=ranked.index)).astype(str),
        "Phase": ranked.apply(_phase, axis=1),
        "S/R Decision": ranked.get("sr_status", pd.Series("—", index=ranked.index)).astype(str).str.replace("_", " "),
        "Evidence": pd.to_numeric(ranked.get("decision_score"), errors="coerce").round(0),
        "Strength": ranked.get("decision_strength", pd.Series("—", index=ranked.index)).astype(str),
        "Move %": pd.to_numeric(ranked.get("price_change_pct"), errors="coerce").round(2),
        "CMP": pd.to_numeric(ranked.get("reference_price"), errors="coerce").round(2),
        "Support": pd.to_numeric(ranked.get("support"), errors="coerce").round(2),
        "Resistance": pd.to_numeric(ranked.get("resistance"), errors="coerce").round(2),
        "Decision": ranked.get("decision_reason", pd.Series("—", index=ranked.index)).astype(str),
    }).head(30)
    st.dataframe(_table_style(table), use_container_width=True, hide_index=True)


def _render_evidence(row: pd.Series):
    st.subheader(f"Decision Evidence — {row['symbol']}")
    cols = st.columns(5)
    for col, (label, value) in zip(cols, [("CMP", row.get("reference_price")), ("Support", row.get("support")), ("Resistance", row.get("resistance")), ("Evidence", row.get("decision_score")), ("S/R", row.get("sr_status", "—"))]):
        with col:
            v = _num(value)
            col.metric(label, "—" if v is None else (f"{v:.0f}" if label == "Evidence" else f"{v:.2f}")) if label != "S/R" else col.metric(label, str(value).replace("_", " "))
    with st.expander("Detailed evidence", expanded=False):
        evidence = pd.DataFrame({
            "Evidence": ["Price/Direction", "First Range", "Futures", "PE-CE OI", "PCR", "IV", "Volume", "S/R", "Straddle"],
            "Interpretation": [row.get("directional_interpretation", "—"), row.get("first_range_event", "—"), row.get("futures_interpretation", "—"), row.get("options_interpretation", "—"), row.get("pcr_interpretation", "—"), row.get("iv_interpretation", "—"), row.get("volume_interpretation", "—"), row.get("sr_interpretation", "—"), row.get("straddle_interpretation", "—")],
        })
        st.dataframe(evidence, use_container_width=True, hide_index=True)


def render():
    st.set_page_config(page_title="NTIS SDL — Intraday Decision Center", layout="wide")
    _css()
    st.markdown('<div class="hero"><div class="hero-title">NTIS SDL — Intraday Decision Center</div><div class="hero-sub">Decision-oriented intraday analysis — developing and confirmed opportunities ranked by evidence strength, direction and support/resistance state.</div></div>', unsafe_allow_html=True)
    source_text = st.text_input("Source folder", value=str(Path(INTRADAY_SOURCE_ROOT).expanduser()))
    source_root = Path(source_text).expanduser()
    c1, c2 = st.columns([1, 2])
    with c1:
        trading_date = st.date_input("Trading date", value=date.today()).strftime("%Y-%m-%d")
    with c2:
        mode = st.radio("Read mode", ["Latest File", "All Files / Day Replay"], horizontal=True)
    try:
        sources = _discover_sources(trading_date, source_root)
    except Exception as exc:
        st.error(f"Source discovery failed: {type(exc).__name__}: {exc}"); return
    if not sources:
        st.warning("No Daywise snapshots found for the selected date."); return
    if mode == "Latest File":
        idx = st.selectbox("Snapshot", list(range(len(sources))), index=len(sources) - 1, format_func=lambda i: f"{parse_observation_timestamp(sources[i]):%H:%M:%S} — {sources[i].name}")
        if st.button("PROCESS SELECTED SNAPSHOT", type="primary", use_container_width=True):
            st.session_state["ds_result"] = process_selected_source(sources[idx], trading_date)
            st.session_state["ds_timeline"] = pd.DataFrame()
    else:
        st.info(f"{len(sources)} snapshots discovered. Replay will process them chronologically.")
        if st.button("PROCESS ALL FILES / DAY REPLAY", type="primary", use_container_width=True):
            try:
                latest, timeline = process_all_sources(sources, trading_date)
                st.session_state["ds_result"] = latest; st.session_state["ds_timeline"] = timeline
            except Exception as exc:
                st.error(f"Replay failed: {type(exc).__name__}: {exc}")
    result = st.session_state.get("ds_result")
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        st.info("Select a mode and process the data."); return
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


if __name__ == "__main__":
    render()
