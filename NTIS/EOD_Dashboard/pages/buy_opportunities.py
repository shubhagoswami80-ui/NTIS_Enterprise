"""
NTIS-EOD
BUY Opportunities Page

Presentation Layer Only
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from EOD_Dashboard.components.intelligence_table import (
    render_intelligence_table,
)
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
    "Target",
    "Stop Loss",
    "NTIS Score",
    "BUY Probability %",
    "SELL Probability %",
    "Probability",
    "Confidence",
    "Validation Score",
    "Pattern",
    "Pattern Reason",
    "Outcome",
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


def _unique_values(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []

    values = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    return sorted(values)


def _filter_buy_candidates(
    df: pd.DataFrame,
    search_term: str,
    confidence_filters: list[str],
    pattern_filters: list[str],
) -> pd.DataFrame:
    filtered = df.copy()

    if confidence_filters and "Confidence" in filtered.columns:
        filtered = filtered[filtered["Confidence"].astype(str).isin(confidence_filters)]

    if pattern_filters and "Pattern" in filtered.columns:
        filtered = filtered[filtered["Pattern"].astype(str).isin(pattern_filters)]

    if search_term:
        search = search_term.strip().lower()
        if search:
            mask = pd.Series(False, index=filtered.index)
            for column in ["Symbol", "Signal", "Pattern", "Pattern Reason", "Outcome"]:
                if column in filtered.columns:
                    mask = mask | filtered[column].astype(str).str.lower().str.contains(search)
            filtered = filtered[mask]

    return filtered


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

    search_term = st.text_input(
        "Search Symbol / Pattern / Outcome",
        value="",
        placeholder="Enter symbol, pattern or outcome",
    )

    confidence_filters = st.multiselect(
        "Confidence",
        options=_unique_values(buy_df, "Confidence"),
        default=_unique_values(buy_df, "Confidence"),
    )

    pattern_filters = st.multiselect(
        "Pattern",
        options=_unique_values(buy_df, "Pattern"),
        default=_unique_values(buy_df, "Pattern"),
    )

    filtered_buy_df = _filter_buy_candidates(
        buy_df,
        search_term,
        confidence_filters,
        pattern_filters,
    )

    show_summary_cards(filtered_buy_df)

    if filtered_buy_df.empty:
        st.info("No BUY opportunities match the selected filters.")
        return

    render_intelligence_table(
        dataframe=filtered_buy_df,
        title="BUY Opportunities",
        preferred_columns=DISPLAY_COLUMNS,
        updated=dataset_info.get("updated"),
        filename="buy_opportunities.csv",
    )


if __name__ == "__main__":
    show_buy_opportunities()