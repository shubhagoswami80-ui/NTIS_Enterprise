"""
NTIS EOD Dashboard Summary Cards

Presentation Layer Only
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


TRADE_VIEW_COLUMN = "Trade View"
CONFIDENCE_COLUMN = "Confidence"


def _count(df: pd.DataFrame, value: str) -> int:
    """
    Safely count values in the Trade View column.
    """

    if TRADE_VIEW_COLUMN not in df.columns:
        return 0

    series = (
        df[TRADE_VIEW_COLUMN]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return int(series.eq(value.upper()).sum())


def _high_confidence(df: pd.DataFrame) -> int:
    """
    Count HIGH confidence records safely.
    """

    if CONFIDENCE_COLUMN not in df.columns:
        return 0

    series = (
        df[CONFIDENCE_COLUMN]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return int(series.eq("HIGH").sum())


def show_summary_cards(df: pd.DataFrame) -> None:
    """
    Render dashboard summary KPI cards.

    Notes
    -----
    UI only.
    No business logic should be implemented here.
    """

    if df is None or df.empty:
        st.warning("No dashboard data available.")
        return

    total = len(df)

    buy = _count(df, "BUY")
    sell = _count(df, "SELL")
    watch = _count(df, "HOLD")
    high_confidence = _high_confidence(df)

    col_total, col_buy, col_sell, col_watch, col_conf = st.columns(5)

    with col_total:
        st.metric(
            label="Total Stocks",
            value=f"{total:,}",
        )

    with col_buy:
        st.metric(
            label="BUY",
            value=buy,
        )

    with col_sell:
        st.metric(
            label="SELL",
            value=sell,
        )

    with col_watch:
        st.metric(
            label="Watchlist",
            value=watch,
        )

    with col_conf:
        st.metric(
            label="High Confidence",
            value=high_confidence,
        )