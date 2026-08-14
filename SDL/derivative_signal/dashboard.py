from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Existing SDL services are reused; they are not copied or modified.
from config import INTRADAY_SOURCE_ROOT, STATE_JSON
from source_loader import discover_daywise_files
from storage import load_state, save_state

from derivative_signal.signal_engine import build_signal

STATE_KEY = "derivative_signal"


def _discover_sources(trading_date: str) -> list[Path]:
    files = discover_daywise_files(INTRADAY_SOURCE_ROOT, trading_date)
    return sorted(
        [Path(p) for p in files if Path(p).is_file()],
        key=lambda p: p.stat().st_mtime,
    )


def _load_source(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _previous(state: dict[str, Any], trading_date: str) -> dict[str, dict]:
    return state.get(STATE_KEY, {}).get(trading_date, {}).get("previous_snapshot", {})


def _snapshot_rows(df: pd.DataFrame) -> dict[str, dict]:
    keep = [
        "Symbol", "Open", "High", "Low", "Close",
        "OI Chg %", "Tot CE OI Chg %", "Tot PE OI Chg %",
        "Tot PE-CE OI Chg",
    ]
    rows: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        symbol = str(record.get("Symbol", "")).strip().upper()
        if symbol:
            rows[symbol] = {k: record.get(k) for k in keep}
    return rows


def process_selected_source(path: Path, trading_date: str) -> pd.DataFrame:
    df = _load_source(path)
    state = load_state(STATE_JSON)
    previous = _previous(state, trading_date)

    results = []
    for record in df.to_dict(orient="records"):
        symbol = str(record.get("Symbol", "")).strip().upper()
        results.append(build_signal(record, previous.get(symbol)))

    day = state.setdefault(STATE_KEY, {}).setdefault(trading_date, {})
    day["previous_snapshot"] = _snapshot_rows(df)
    day["source_file"] = str(path)
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)

    return pd.DataFrame(results)


def render() -> None:
    st.title("NTIS SDL — Decision Signals")
    st.caption(
        "Separate directional evidence layer. Existing SDL and Straddle Breakout logic are untouched."
    )

    selected_date = st.date_input(
        "Trading date",
        value=date.today(),
        key="ds_trading_date",
    )
    trading_date = selected_date.isoformat()

    sources = _discover_sources(trading_date)
    if not sources:
        st.info("No eligible Daywise source files found for the selected date.")
        return

    labels = [p.name for p in sources]
    selected_label = st.selectbox("Source file", labels, key="ds_source_file")
    selected_path = sources[labels.index(selected_label)]

    st.caption(
        f"Source: {selected_path.name} | "
        f"Modified: {datetime.fromtimestamp(selected_path.stat().st_mtime):%d %b %Y, %H:%M:%S}"
    )

    if st.button(
        "▶ Process Selected Data",
        type="primary",
        width="stretch",
        key="ds_process_selected",
    ):
        try:
            st.session_state["ds_result"] = process_selected_source(
                selected_path, trading_date
            )
            st.session_state["ds_source"] = selected_path.name
            st.success(f"Processed {selected_path.name}")
        except Exception as exc:
            st.error(f"Processing failed: {type(exc).__name__}: {exc}")

    result = st.session_state.get("ds_result")
    if result is None or result.empty:
        st.info("Select a source and press Process Selected Data.")
        return

    st.subheader("Decision Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Candidates", len(result))
    c2.metric("Bullish", int((result.direction == "BULLISH").sum()))
    c3.metric("Bearish", int((result.direction == "BEARISH").sum()))
    c4.metric("Developing", int((result.state == "DEVELOPING").sum()))
    c5.metric("No Trade", int((result.state == "NO_TRADE").sum()))

    direction = st.selectbox(
        "Direction", ["ALL", "BULLISH", "BEARISH", "NEUTRAL"], key="ds_direction"
    )
    state_filter = st.selectbox(
        "Decision State",
        ["ALL", "WATCH", "DEVELOPING", "CONFIRMED", "NO_TRADE", "INSUFFICIENT_DATA"],
        key="ds_state",
    )

    filtered = result.copy()
    if direction != "ALL":
        filtered = filtered[filtered.direction == direction]
    if state_filter != "ALL":
        filtered = filtered[filtered.state == state_filter]

    display_cols = [
        "symbol", "direction", "price_event", "oi_evidence",
        "options_structure", "location", "state", "reference_price",
    ]
    st.dataframe(
        filtered[display_cols].rename(
            columns={
                "symbol": "Symbol",
                "direction": "Direction",
                "price_event": "Price Event",
                "oi_evidence": "OI Evidence",
                "options_structure": "PE-CE Evidence",
                "location": "Location",
                "state": "Decision",
                "reference_price": "Reference Price",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Why?")
    if not filtered.empty:
        symbol = st.selectbox(
            "Candidate", filtered.symbol.tolist(), key="ds_candidate"
        )
        row = filtered.loc[filtered.symbol == symbol].iloc[0]
        st.write(f"**{symbol} — {row.state}** | {row.direction} | {row.price_event}")
        for reason in row.reasons:
            st.write(f"- {reason}")

    st.caption(
        f"Source: {st.session_state.get('ds_source', selected_path.name)} | "
        "Explicit Futures OI is not inferred from primary OI."
    )
