"""
NTIS-EOD
BUY Opportunities Page

Presentation Layer Only
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from EOD_Dashboard.data.data_loader import (
    load_dataset,
    get_dataset_info,
)

from EOD_Dashboard.components.summary_cards import (
    show_summary_cards,
)


PAGE_TITLE = "NTIS BUY OPPORTUNITIES"

SIGNAL_COLUMNS = (
    "Trade View",
    "Signal",
    "Final Signal",
    "Trade Bias",
    "Validation Signal",
)

DISPLAY_COLUMNS = (
    "Rank",
    "Symbol",
    "CMP",
    "Entry Close",
    "NTIS Score",
    "BUY Probability %",
    "Probability",
    "Confidence",
    "Support Strike",
    "Resistance Strike",
)


def _map_signal(value: object) -> str:
    """
    Normalize backend signal values.
    """

    mapping = {
        "BUY": "BUY",
        "BULLISH": "BUY",
        "LONG": "BUY",
        "SELL": "SELL",
        "BEARISH": "SELL",
        "SHORT": "SELL",
    }

    return mapping.get(str(value).strip().upper(), "HOLD")


def _find_signal_column(df: pd.DataFrame) -> str | None:
    """
    Locate the first available signal column.
    """

    for column in SIGNAL_COLUMNS:
        if column in df.columns:
            return column

    return None


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare presentation dataframe.

    Backend logic is intentionally unchanged.
    """

    df = df.copy()

    signal_column = _find_signal_column(df)

    if signal_column:
        df["Trade View"] = df[signal_column].apply(_map_signal)
    else:
        df["Trade View"] = "HOLD"

    return df


def _display_buy_table(df: pd.DataFrame) -> None:
    """
    Display BUY opportunities.
    """

    st.subheader("BUY Opportunities")

    if df.empty:
        st.info("No BUY opportunities available.")
        return

    columns = [c for c in DISPLAY_COLUMNS if c in df.columns]

    if not columns:
        columns = list(df.columns)

    st.dataframe(
        df[columns],
        hide_index=True,
        use_container_width=True,
    )


def show_buy_opportunities() -> None:
    """
    BUY Opportunities dashboard page.
    """

    st.header(PAGE_TITLE)

    dataframe = load_dataset("ranking")

    if dataframe is None or dataframe.empty:
        st.warning("Ranking dataset not available.")
        return

    dataframe = _prepare_dataframe(dataframe)

    buy_df = dataframe[
        dataframe["Trade View"] == "BUY"
    ].copy()

    show_summary_cards(buy_df)

    dataset_info = get_dataset_info("ranking") or {}

    if dataset_info.get("available"):
        st.caption(
            f"Last Updated : {dataset_info.get('updated')}"
        )

    st.markdown(
        f"### Total BUY Opportunities : **{len(buy_df):,}**"
    )

    _display_buy_table(buy_df)


if __name__ == "__main__":
    show_buy_opportunities()