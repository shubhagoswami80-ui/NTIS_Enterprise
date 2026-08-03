"""
NTIS-EOD
Intelligence Charts Component

Presentation Layer Only

Shared visualization component for:

    - NTIS Score distribution
    - Signal distribution
    - Confidence distribution
    - Probability analysis

Rules:
    - No backend logic
    - No calculations
    - No data modification
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.express as px


def render_signal_distribution(
    dataframe: pd.DataFrame,
) -> None:
    """
    Display signal distribution chart.
    """

    if dataframe is None or dataframe.empty:
        return

    if "Signal" not in dataframe.columns:
        return

    signal_count = (
        dataframe["Signal"]
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .reset_index()
    )

    signal_count.columns = [
        "Signal",
        "Count",
    ]

    fig = px.bar(
        signal_count,
        x="Signal",
        y="Count",
        title="Signal Distribution",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def render_confidence_distribution(
    dataframe: pd.DataFrame,
) -> None:
    """
    Display confidence distribution chart.
    """

    if dataframe is None or dataframe.empty:
        return

    if "Confidence" not in dataframe.columns:
        return

    confidence_count = (
        dataframe["Confidence"]
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .reset_index()
    )

    confidence_count.columns = [
        "Confidence",
        "Count",
    ]

    fig = px.bar(
        confidence_count,
        x="Confidence",
        y="Count",
        title="Confidence Distribution",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def render_ntis_score_distribution(
    dataframe: pd.DataFrame,
) -> None:
    """
    Display NTIS score distribution.
    """

    if dataframe is None or dataframe.empty:
        return

    if "NTIS Score" not in dataframe.columns:
        return

    fig = px.histogram(
        dataframe,
        x="NTIS Score",
        title="NTIS Score Distribution",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def render_probability_distribution(
    dataframe: pd.DataFrame,
) -> None:
    """
    Display probability distribution.
    """

    if dataframe is None or dataframe.empty:
        return

    probability_columns = [
        column
        for column in (
            "BUY Probability %",
            "SELL Probability %",
            "Probability",
        )
        if column in dataframe.columns
    ]

    if not probability_columns:
        return

    fig = px.histogram(
        dataframe,
        x=probability_columns[0],
        title="Probability Distribution",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )