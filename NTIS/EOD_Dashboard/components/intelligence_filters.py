"""
NTIS-EOD
Intelligence Filters Component

Presentation Layer Only

Shared filtering component for:

    - BUY Intelligence
    - SELL Intelligence
    - Probability Ranking
    - Pattern Intelligence
    - OI Intelligence
    - Support / Resistance Intelligence

Rules:
    - No backend logic
    - No calculations
    - No data modification
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _unique_values(
    dataframe: pd.DataFrame,
    column: str,
) -> list[str]:
    """
    Return sorted unique values safely.
    """

    if column not in dataframe.columns:
        return []

    values = (
        dataframe[column]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    return sorted(values)


def render_intelligence_filters(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Render common dashboard filters.

    Returns filtered copy.

    No source dataframe mutation.
    """

    if dataframe is None or dataframe.empty:
        return dataframe

    filtered = dataframe.copy()

    st.sidebar.subheader(
        "Intelligence Filters"
    )

    # Symbol filter

    if "Symbol" in filtered.columns:

        symbols = _unique_values(
            filtered,
            "Symbol",
        )

        selected_symbols = st.sidebar.multiselect(
            "Symbol",
            symbols,
            default=[],
        )

        if selected_symbols:

            filtered = filtered[
                filtered["Symbol"]
                .astype(str)
                .isin(selected_symbols)
            ]


    # Signal filter

    if "Signal" in filtered.columns:

        signals = _unique_values(
            filtered,
            "Signal",
        )

        selected_signals = st.sidebar.multiselect(
            "Signal",
            signals,
            default=[],
        )

        if selected_signals:

            filtered = filtered[
                filtered["Signal"]
                .astype(str)
                .isin(selected_signals)
            ]


    # Confidence filter

    if "Confidence" in filtered.columns:

        confidence = _unique_values(
            filtered,
            "Confidence",
        )

        selected_confidence = st.sidebar.multiselect(
            "Confidence",
            confidence,
            default=[],
        )

        if selected_confidence:

            filtered = filtered[
                filtered["Confidence"]
                .astype(str)
                .isin(selected_confidence)
            ]


    return filtered