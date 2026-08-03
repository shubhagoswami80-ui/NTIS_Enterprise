"""
NTIS-Intraday Dashboard
Refactored entry point.

UI layout and backend behaviour remain unchanged.
"""

import streamlit as st

from dashboard.dashboard_loader import load_dashboard_data
from dashboard.dashboard_sidebar import build_sidebar_filters

ctx = load_dashboard_data()

status = ctx["status"]
snapshot_date = ctx["snapshot_date"]

trade_df = ctx["trade_df"]
prob_df = ctx["prob_df"]
evolution_df = ctx["evolution_df"]

filtered_trade_df = build_sidebar_filters(trade_df)

# ==========================================================
# APPROVED DASHBOARD LAYOUT (UI ONLY)
# Backend logic unchanged
# ==========================================================

st.title("NTIS Intraday Dashboard")

st.caption(f"Snapshot : {snapshot_date}")

buy_count = sell_count = watch_count = 0

if not trade_df.empty and "Validation Signal" in trade_df.columns:
    buy_count = trade_df["Validation Signal"].eq("VALID BUY").sum()
    sell_count = trade_df["Validation Signal"].eq("VALID SELL").sum()
    watch_count = trade_df["Validation Signal"].eq("WATCH").sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Stocks", len(trade_df))
k2.metric("BUY", buy_count)
k3.metric("SELL", sell_count)
k4.metric("WATCH", watch_count)

st.divider()

left, right = st.columns([2.6, 1.4])

with left:
    st.subheader("Intraday Trade Opportunities")

    display_cols = [
        c for c in [
            "Symbol",
            "Pattern",
            "Intraday Probability %",
            "Confidence",
            "Validation Signal",
            "Entry Price",
            "Stop Loss",
            "Target",
        ] if c in filtered_trade_df.columns
    ]

    st.dataframe(
        filtered_trade_df[display_cols],
        use_container_width=True,
        height=650,
    )

with right:
    st.subheader("Snapshot")
    st.info(
        f"Status : {status.get('status')}\n\nSnapshot Date : {snapshot_date}"
    )

    st.subheader("Probability Ranking")
    if (
        not prob_df.empty
        and "Symbol" in prob_df.columns
        and "Intraday Probability %" in prob_df.columns
    ):
        st.bar_chart(
            prob_df.set_index("Symbol")["Intraday Probability %"].head(15)
        )

    st.subheader("Signal Evolution")
    if not evolution_df.empty:
        st.dataframe(
            evolution_df.head(10),
            use_container_width=True,
            height=240,
        )

st.divider()

if (
    not filtered_trade_df.empty
    and "Symbol" in filtered_trade_df.columns
):
    symbol = st.selectbox(
        "Selected Symbol",
        filtered_trade_df["Symbol"],
    )

    row = filtered_trade_df[
        filtered_trade_df["Symbol"] == symbol
    ].iloc[0]

    st.subheader("Trade Details")
    st.json(row.to_dict())
