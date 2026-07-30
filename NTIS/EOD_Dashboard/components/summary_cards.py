import streamlit as st
import pandas as pd


def _count(df: pd.DataFrame, value: str) -> int:
    """
    Count Trade View values safely.
    """

    if "Trade View" not in df.columns:
        return 0

    return int(
        df["Trade View"]
        .fillna("")
        .astype(str)
        .str.upper()
        .eq(value.upper())
        .sum()
    )


def _high_confidence(df: pd.DataFrame) -> int:

    if "Confidence" not in df.columns:
        return 0

    return int(
        df["Confidence"]
        .fillna("")
        .astype(str)
        .str.upper()
        .eq("HIGH")
        .sum()
    )


def show_summary_cards(df: pd.DataFrame):

    if df is None or df.empty:
        st.warning("No dashboard data available.")
        return

    total = len(df)

    buy = _count(df, "BUY")
    sell = _count(df, "SELL")
    watch = _count(df, "HOLD")

    high_conf = _high_confidence(df)

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Total Stocks", f"{total:,}")
    c2.metric("BUY", buy)
    c3.metric("SELL", sell)
    c4.metric("Watchlist", watch)
    c5.metric("High Confidence", high_conf)