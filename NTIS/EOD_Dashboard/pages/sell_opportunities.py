"""
NTIS-EOD
SELL Opportunities Page

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

from EOD_Dashboard.components.intelligence_table import (
    render_intelligence_table,
)


PAGE_TITLE = "NTIS SELL OPPORTUNITIES"

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
    "SELL Probability %",
    "Probability",
    "Confidence",
    "Support Strike",
    "Resistance Strike",
)


def _normalize_signal(value: object) -> str:
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
    for column in SIGNAL_COLUMNS:
        if column in df.columns:
            return column

    return None


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    signal_column = _find_signal_column(df)

    if signal_column:
        df["Trade View"] = df[signal_column].apply(_normalize_signal)
    else:
        df["Trade View"] = "HOLD"

    return df


def show_sell_opportunities() -> None:

    st.header(PAGE_TITLE)

    dataframe = load_dataset("ranking")

    if dataframe is None or dataframe.empty:
        st.warning("Ranking dataset not available.")
        return

    dataframe = _prepare(dataframe)

    sell_df = dataframe[
        dataframe["Trade View"] == "SELL"
    ].copy()

    show_summary_cards(sell_df)

    dataset_info = get_dataset_info("ranking") or {}

    render_intelligence_table(
        dataframe=sell_df,
        title="SELL Opportunities",
        preferred_columns=DISPLAY_COLUMNS,
        updated=dataset_info.get("updated"),
        filename="sell_opportunities.csv",
    )


if __name__ == "__main__":
    show_sell_opportunities()