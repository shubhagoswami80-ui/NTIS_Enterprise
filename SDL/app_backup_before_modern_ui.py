from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import EVENT_CSV
from pipeline import (
    discover_historical_snapshots,
    process_latest_snapshot_for_today,
)
from storage import load_events

st.set_page_config(
    page_title="SDL Straddle Breakout",
    layout="wide",
)

st.title("SDL — Straddle Breakout")
st.caption("Phase-1 breakout monitoring and historical breakout evidence")

# Manual refresh is intentional for Phase-1.
# Automatic file watching/polling will be added later.
if "latest_workbook" not in st.session_state:
    st.session_state.latest_workbook = None
if "latest_file_mtime" not in st.session_state:
    st.session_state.latest_file_mtime = None
if "last_processed_at" not in st.session_state:
    st.session_state.last_processed_at = None
if "last_process_note" not in st.session_state:
    st.session_state.last_process_note = None

if st.button("Process Latest Snapshot", type="primary", width="stretch"):
    try:
        latest, new_events, df, note = process_latest_snapshot_for_today()

        if latest is None:
            st.warning(note)
            st.session_state.latest_workbook = None
            st.session_state.latest_file_mtime = None
            st.session_state.last_process_note = note
        else:
            latest = Path(latest)
            st.session_state.latest_workbook = str(latest)
            st.session_state.latest_file_mtime = datetime.fromtimestamp(
                latest.stat().st_mtime
            )
            st.session_state.last_processed_at = datetime.now()
            st.session_state.last_process_note = note
            st.success(f"Processed latest workbook: {latest.name}")
            st.caption(note)

        st.rerun()
    except Exception as exc:
        st.error(f"Refresh failed: {exc}")

# ---------------------------------------------------------------------------
# Latest snapshot status
# ---------------------------------------------------------------------------
st.subheader("Latest Snapshot")

status_c1, status_c2, status_c3 = st.columns(3)

if st.session_state.latest_workbook:
    latest_path = Path(st.session_state.latest_workbook)
    status_c1.metric("Latest Workbook", latest_path.name)

    if st.session_state.latest_file_mtime is not None:
        status_c2.metric(
            "File Modified",
            st.session_state.latest_file_mtime.strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        status_c2.metric("File Modified", "—")

    if st.session_state.last_processed_at is not None:
        status_c3.metric(
            "Last Processed",
            st.session_state.last_processed_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        status_c3.metric("Last Processed", "—")

    st.caption(
        "File Modified is the operational filesystem timestamp used to select "
        "the latest workbook; it is not claimed to be market observation time."
    )
else:
    status_c1.metric("Latest Workbook", "Not processed")
    status_c2.metric("File Modified", "—")
    status_c3.metric("Last Processed", "—")

if st.session_state.last_process_note:
    st.caption(st.session_state.last_process_note)

events = load_events(EVENT_CSV)
if events is None:
    events = pd.DataFrame()

today = pd.Timestamp.now().date().isoformat()
today_events = (
    events[events["trading_date"].astype(str) == today].copy()
    if not events.empty and "trading_date" in events.columns
    else pd.DataFrame()
)

c1, c2, c3 = st.columns(3)
c1.metric("Today's Breakouts", len(today_events))
c2.metric(
    "UP",
    int((today_events["direction"] == "UP").sum())
    if not today_events.empty
    else 0,
)
c3.metric(
    "DOWN",
    int((today_events["direction"] == "DOWN").sum())
    if not today_events.empty
    else 0,
)

st.subheader("Today's Straddle Breakouts")

if today_events.empty:
    st.info("No recorded straddle breakouts for today.")
else:
    visible = [
        c
        for c in [
            "observation_timestamp",
            "symbol",
            "direction",
            "open_price",
            "current_price",
            "opening_straddle_premium",
            "expected_1x_price",
            "breakout_distance",
        ]
        if c in today_events.columns
    ]
    st.dataframe(
        today_events[visible],
        width="stretch",
        hide_index=True,
    )

st.subheader("Earlier Straddle Breakouts")

if events.empty:
    st.info("No historical breakout events recorded yet.")
else:
    dates = sorted(
        events["trading_date"].astype(str).dropna().unique(),
        reverse=True,
    )
    selected = st.selectbox("Trading date", dates)
    historical = events[
        events["trading_date"].astype(str) == selected
    ].copy()

    visible = [
        c
        for c in [
            "observation_timestamp",
            "symbol",
            "direction",
            "open_price",
            "current_price",
            "opening_straddle_premium",
            "expected_1x_price",
            "breakout_distance",
            "strategy_version",
        ]
        if c in historical.columns
    ]
    st.dataframe(
        historical[visible],
        width="stretch",
        hide_index=True,
    )

st.caption(
    "Phase-1 only: no SL, target outcome, success/failure or P&L is calculated."
)
