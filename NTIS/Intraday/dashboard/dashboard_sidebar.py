"""
NTIS-Intraday Dashboard Sidebar

UI-only sidebar helpers extracted from intraday_dashboard.py.
Business logic intentionally unchanged.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd


def build_sidebar_filters(trade_df: pd.DataFrame) -> pd.DataFrame:
    """
    Render sidebar filters and return the filtered dataframe.
    """

    if trade_df.empty:
        return trade_df

    df = trade_df.copy()

    st.sidebar.header("Filters")

    if "Validation Signal" in df.columns:
        signals = sorted(df["Validation Signal"].dropna().unique().tolist())
        selected = st.sidebar.multiselect(
            "Validation Signal",
            options=signals,
            default=signals,
        )
        if selected:
            df = df[df["Validation Signal"].isin(selected)]

    if "Pattern" in df.columns:
        patterns = sorted(df["Pattern"].dropna().unique().tolist())
        selected = st.sidebar.multiselect(
            "Pattern",
            options=patterns,
            default=patterns,
        )
        if selected:
            df = df[df["Pattern"].isin(selected)]

    if "Intraday Probability %" in df.columns:
        lo = float(df["Intraday Probability %"].min())
        hi = float(df["Intraday Probability %"].max())
        minimum = st.sidebar.slider(
            "Minimum Probability %",
            min_value=lo,
            max_value=hi,
            value=lo,
        )
        df = df[df["Intraday Probability %"] >= minimum]

    return df
