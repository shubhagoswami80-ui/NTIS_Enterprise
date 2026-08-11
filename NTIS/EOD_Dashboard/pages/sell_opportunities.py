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
    "Target",
    "Stop Loss",
    "NTIS Score",
    "SELL Probability %",
    "BUY Probability %",
    "Probability",
    "Confidence",
    "Validation Score",
    "Pattern",
    "Pattern Reason",
    "Outcome",
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


def _filter_sell_candidates(
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

    st.markdown(
        f"### Total SELL Opportunities : **{len(sell_df):,}**"
    )

    search_term = st.text_input(
        "Search Symbol / Pattern / Outcome",
        value="",
        placeholder="Enter symbol, pattern or outcome",
    )

    confidence_filters = st.multiselect(
        "Confidence",
        options=_unique_values(sell_df, "Confidence"),
        default=_unique_values(sell_df, "Confidence"),
    )

    pattern_filters = st.multiselect(
        "Pattern",
        options=_unique_values(sell_df, "Pattern"),
        default=_unique_values(sell_df, "Pattern"),
    )

    filtered_sell_df = _filter_sell_candidates(
        sell_df,
        search_term,
        confidence_filters,
        pattern_filters,
    )

    show_summary_cards(filtered_sell_df)

    if filtered_sell_df.empty:
        st.info("No SELL opportunities match the selected filters.")
        return

    render_intelligence_table(
        dataframe=filtered_sell_df,
        title="SELL Opportunities",
        preferred_columns=DISPLAY_COLUMNS,
        updated=dataset_info.get("updated"),
        filename="sell_opportunities.csv",
    )


if __name__ == "__main__":
    show_sell_opportunities()