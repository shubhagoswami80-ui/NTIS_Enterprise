from __future__ import annotations

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

if st.button("Refresh Today's Statistics", type="primary", use_container_width=True):
    try:
        latest, new_events, df, note = process_latest_snapshot_for_today()
        if latest is None:
            st.warning(note)
        else:
            st.success(f"Processed latest workbook: {latest.name}")
            st.caption(note)
            st.rerun()
    except Exception as exc:
        st.error(f"Refresh failed: {exc}")

events = load_events(EVENT_CSV)
if events is None:
    events = pd.DataFrame()

today = pd.Timestamp.now().date().isoformat()
today_events = events[events["trading_date"].astype(str) == today].copy() if not events.empty and "trading_date" in events.columns else pd.DataFrame()

c1, c2, c3 = st.columns(3)
c1.metric("Today's Breakouts", len(today_events))
c2.metric("UP", int((today_events["direction"] == "UP").sum()) if not today_events.empty else 0)
c3.metric("DOWN", int((today_events["direction"] == "DOWN").sum()) if not today_events.empty else 0)

st.subheader("Today's Straddle Breakouts")
if today_events.empty:
    st.info("No recorded straddle breakouts for today.")
else:
    visible = [
        c for c in [
            "observation_timestamp",
            "symbol",
            "direction",
            "open_price",
            "current_price",
            "opening_straddle_premium",
            "expected_1x_price",
            "breakout_distance",
        ] if c in today_events.columns
    ]
    st.dataframe(today_events[visible], use_container_width=True, hide_index=True)

st.subheader("Earlier Straddle Breakouts")
if events.empty:
    st.info("No historical breakout events recorded yet.")
else:
    dates = sorted(events["trading_date"].astype(str).dropna().unique(), reverse=True)
    selected = st.selectbox("Trading date", dates)
    historical = events[events["trading_date"].astype(str) == selected].copy()
    visible = [
        c for c in [
            "observation_timestamp",
            "symbol",
            "direction",
            "open_price",
            "current_price",
            "opening_straddle_premium",
            "expected_1x_price",
            "breakout_distance",
            "strategy_version",
        ] if c in historical.columns
    ]
    st.dataframe(historical[visible], use_container_width=True, hide_index=True)

st.caption("Phase-1 only: no SL, target outcome, success/failure or P&L is calculated.")
