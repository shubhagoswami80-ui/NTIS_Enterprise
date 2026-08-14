from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
import sys
import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from multi_source_adapter import discover_sources, load_and_merge
from signal_engine import build_signal


def _extract_date_tokens(value: str) -> set[str]:
    text = str(value)
    tokens: set[str] = set()
    for m in re.findall(r"\d{4}-\d{2}-\d{2}", text):
        tokens.add(m)
    for m in re.findall(r"\d{2}-\d{2}-\d{4}", text):
        try:
            tokens.add(pd.to_datetime(m, dayfirst=True).strftime("%Y-%m-%d"))
        except Exception:
            pass
    for m in re.findall(r"\d{2}_\d{1,2}_\d{4}", text):
        try:
            tokens.add(pd.to_datetime(m, dayfirst=True, format="%d_%m_%Y").strftime("%Y-%m-%d"))
        except Exception:
            pass
    return tokens


def _discover_available_dates(folder: Path) -> list[date]:
    dates: set[date] = set()
    if not folder.exists() or not folder.is_dir():
        return []
    candidates = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
            candidates.append(p)
    for p in candidates:
        for token in _extract_date_tokens(p.name):
            try:
                dates.add(pd.Timestamp(token).date())
            except Exception:
                pass
    for p in folder.iterdir():
        if p.is_dir():
            try:
                d = pd.to_datetime(p.name, errors="raise").date()
                dates.add(d)
            except Exception:
                pass
    return sorted(dates)


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _straddle_progress(row: dict) -> float | None:
    value = _safe_float(row.get("straddle_progress_pct"))
    if value is not None:
        return value
    opening = _safe_float(row.get("opening_straddle_premium"))
    open_price = _safe_float(row.get("open"))
    close = _safe_float(row.get("close"))
    if opening in (None, 0) or open_price is None or close is None:
        return None
    return abs(close - open_price) / opening * 100.0


def _prepare_rows(bundle):
    if bundle.rows is None or bundle.rows.empty:
        return pd.DataFrame()
    rows = bundle.rows.copy()
    rows["straddle_progress_pct"] = rows.apply(lambda r: _straddle_progress(r.to_dict()), axis=1)
    for c in ("support", "resistance"):
        if c not in rows.columns:
            rows[c] = pd.NA
    return pd.DataFrame([build_signal(r.to_dict()) for _, r in rows.iterrows()])


def _decision(row):
    state = str(row.get("state", ""))
    direction = str(row.get("direction", ""))
    if state == "STRONG_BULLISH":
        return "🟢 STRONG BULLISH"
    if state == "STRONG_BEARISH":
        return "🔴 STRONG BEARISH"
    if state == "STRONG_NEAR_LEVEL":
        return "🟢🟠 STRONG BULLISH — NEAR LEVEL" if direction == "BULLISH" else "🔴🟠 STRONG BEARISH — NEAR LEVEL"
    if state == "ACTIVE_BULLISH":
        return "🟢 BULLISH"
    if state == "ACTIVE_BEARISH":
        return "🔴 BEARISH"
    if state == "WAIT_BREAK_CONFIRMATION":
        return "🟠 WAIT — LEVEL CONFIRMATION"
    if state == "DIRECTIONAL_UNCONFIRMED":
        return "🟣 CONFLICT / INCOMPLETE"
    if state == "INSUFFICIENT_DATA":
        return "⚪ NO SIGNAL"
    return "🟡 DEVELOPING"


def _style(row):
    label = str(row.get("_decision", ""))
    if "STRONG BULLISH" in label or label == "🟢 BULLISH":
        return ["background-color:#e1f5e6;color:#14532d;font-weight:700"] * len(row)
    if "STRONG BEARISH" in label or label == "🔴 BEARISH":
        return ["background-color:#fbe0e0;color:#991b1b;font-weight:700"] * len(row)
    if "CONFLICT" in label:
        return ["background-color:#eee8ff;color:#5b21b6;font-weight:700"] * len(row)
    if "WAIT" in label or "DEVELOPING" in label:
        return ["background-color:#fff4df;color:#9a6700;font-weight:700"] * len(row)
    return ["background-color:#f3f4f6;color:#555"] * len(row)


def render():
    st.title("NTIS SDL — Decision Dashboard")
    st.caption(
        "Trading-oriented multi-source decision layer. Existing SDL pipeline remains read-only and unchanged."
    )

    st.subheader("1. Source & Date")
    source_folder = st.text_input(
        "Source folder",
        value=st.session_state.get("ds_source_folder", ""),
        placeholder=r"D:\My-data\Share_P&L\Ichart Data\Screenshot\August26\2026-08-15",
        key="ds_source_folder",
    )

    folder = Path(source_folder.strip()) if source_folder.strip() else None
    available_dates = _discover_available_dates(folder) if folder else []

    latest_hint = max(available_dates) if available_dates else None
    default_date = latest_hint or date.today()

    selected_date = st.date_input(
        "Trading date",
        value=st.session_state.get("ds_date", default_date),
        key="ds_date",
    )

    use_latest = st.checkbox(
        "Use latest available date if selected date has no source data",
        value=False,
        key="ds_latest_fallback",
    )

    c1, c2 = st.columns(2)
    if c1.button("🔎 SCAN SELECTED DATE", width="stretch"):
        st.session_state.pop("ds_bundle", None)
        st.session_state["ds_scanned_date"] = selected_date.isoformat()

    if c2.button("📅 LOAD LATEST AVAILABLE", width="stretch"):
        if available_dates:
            st.session_state["ds_date"] = max(available_dates)
            st.session_state["ds_bundle"] = None
            st.rerun()
        else:
            st.warning("No dated Excel source files were discovered in the selected folder.")

    if folder is None:
        st.info("Enter the existing daily/root source folder. No separate source folders are required.")
        return
    if not folder.exists():
        st.error(f"Source folder does not exist: {folder}")
        return

    trading_date = selected_date.isoformat()
    bundle = discover_sources(folder, trading_date)

    if not bundle.files and use_latest and available_dates:
        latest = max(available_dates)
        if latest.isoformat() != trading_date:
            trading_date = latest.isoformat()
            st.warning(f"No source files found for {selected_date}. Using latest available date: {latest}.")
            bundle = discover_sources(folder, trading_date)

    st.subheader("2. Source Readiness")
    roles = ["BASE", "FUTURES", "IV", "SUPPORT", "RESISTANCE", "VOLUME"]
    cols = st.columns(6)
    for col, role in zip(cols, roles):
        col.metric(role, "FOUND" if bundle.files.get(role) else "MISSING")

    if bundle.files:
        with st.expander("Files selected for processing", expanded=True):
            for role, path in bundle.files.items():
                st.write(f"**{role}:** `{path.name}`")
    if bundle.missing:
        st.warning("Required source families missing: " + ", ".join(bundle.missing))
    for error in bundle.errors:
        st.error(error)

    if st.button("▶ PROCESS SELECTED DATE", type="primary", width="stretch"):
        processed = load_and_merge(bundle)
        st.session_state["ds_bundle"] = processed
        st.session_state["ds_processed_date"] = trading_date

    bundle = st.session_state.get("ds_bundle")
    if bundle is None:
        if bundle is not None:
            pass
        st.info("Review source readiness and press PROCESS SELECTED DATE.")
        return
    if bundle.rows is None or bundle.rows.empty:
        st.error("No merged symbol data is available.")
        return

    result = _prepare_rows(bundle)
    if result.empty:
        st.error("Decision engine returned no records.")
        return

    result["_decision"] = result.apply(_decision, axis=1)

    st.success(
        f"Processed {len(result)} symbols for {st.session_state.get('ds_processed_date', trading_date)} "
        f"from {len(bundle.files)} available source families."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Symbols", len(result))
    c2.metric("Strong Bullish", int(result.state.eq("STRONG_BULLISH").sum()))
    c3.metric("Bullish", int(result.state.isin(["ACTIVE_BULLISH", "STRONG_NEAR_LEVEL"]).sum()))
    c4.metric("Strong Bearish", int(result.state.eq("STRONG_BEARISH").sum()))
    c5.metric("Conflict/Incomplete", int(result.state.isin(["DIRECTIONAL_UNCONFIRMED", "INSUFFICIENT_DATA"]).sum()))

    st.subheader("3. Bias Filter")

    categories = [
        "ALL",
        "STRONG BULLISH",
        "BULLISH",
        "MILD BULLISH",
        "DEVELOPING BULLISH",
        "CONFLICT",
        "NEUTRAL / NO SIGNAL",
        "DEVELOPING BEARISH",
        "MILD BEARISH",
        "BEARISH",
        "STRONG BEARISH",
    ]
    bias = st.selectbox("Bias Category", categories, key="ds_bias")

    filtered = result.copy()

    def bias_of(row):
        s = str(row.get("state", ""))
        d = str(row.get("direction", ""))
        if s == "STRONG_BULLISH": return "STRONG BULLISH"
        if s == "STRONG_BEARISH": return "STRONG BEARISH"
        if s == "ACTIVE_BULLISH": return "BULLISH"
        if s == "ACTIVE_BEARISH": return "BEARISH"
        if s == "STRONG_NEAR_LEVEL": return "BULLISH" if d == "BULLISH" else "BEARISH"
        if s == "DIRECTIONAL_UNCONFIRMED": return "CONFLICT"
        if s == "INSUFFICIENT_DATA": return "NEUTRAL / NO SIGNAL"
        if d == "BULLISH": return "MILD BULLISH"
        if d == "BEARISH": return "MILD BEARISH"
        return "NEUTRAL / NO SIGNAL"

    filtered["_bias"] = filtered.apply(bias_of, axis=1)
    if bias != "ALL":
        filtered = filtered[filtered["_bias"] == bias]

    if filtered.empty:
        st.info(f"No stocks currently match: {bias}")
        return

    filtered = filtered.sort_values(
        ["strength", "price_change_pct"], ascending=[False, False], na_position="last"
    )

    table = pd.DataFrame({
        "Symbol": filtered.symbol,
        "Bias": filtered["_bias"],
        "Decision": filtered["_decision"],
        "Price %": filtered.price_change_pct,
        "PE-CE OI": filtered.options_structure,
        "Futures": filtered.futures_buildup,
        "Fut OI %": filtered.futures_oi_change_pct,
        "Support": filtered.support,
        "Resistance": filtered.resistance,
        "S/R": filtered.location,
        "Straddle Progress %": filtered.straddle_progress_pct,
        "Straddle Stage": filtered.straddle_stage,
        "Evidence": filtered.evidence_quality,
        "Strength": filtered.strength,
    })
    table["_state"] = filtered.state.values
    table["_decision"] = filtered["_decision"].values

    st.dataframe(
        table.style.apply(_style, axis=1),
        width="stretch",
        hide_index=True,
        column_config={
            "Price %": st.column_config.NumberColumn(format="%.2f%%"),
            "Fut OI %": st.column_config.NumberColumn(format="%.2f%%"),
            "Straddle Progress %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    st.subheader("Decision Detail")
    symbol_options = filtered.symbol.tolist()
    symbol = st.selectbox("Symbol", symbol_options, key="ds_symbol")
    row = filtered.loc[filtered.symbol == symbol].iloc[0]
    st.markdown(f"### {_decision(row)}")
    st.write(f"**Bias:** {row['_bias']}")
    st.write(f"**Price:** {row['price_change_pct']:.2f}%" if pd.notna(row["price_change_pct"]) else "**Price:** unavailable")
    for reason in row.reasons:
        st.write(f"- {reason}")


if __name__ == "__main__":
    render()
