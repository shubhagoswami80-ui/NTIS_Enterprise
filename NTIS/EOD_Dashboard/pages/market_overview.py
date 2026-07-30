import streamlit as st
import pandas as pd

from EOD_Dashboard.data.data_loader import (
    load_dataset,
    get_dataset_info,
)
from EOD_Dashboard.components.dashboard_cards import show_cards


def map_signal(value):

    value = str(value).strip().upper()

    mapping = {
        "BULLISH": "BUY",
        "BUY": "BUY",
        "LONG": "BUY",
        "BEARISH": "SELL",
        "SELL": "SELL",
        "SHORT": "SELL",
    }

    return mapping.get(value, "HOLD")


def _first_available(df, columns):

    for column in columns:
        if column in df.columns:
            return column

    return None


def _display_table(df, title):

    st.subheader(title)

    if df.empty:
        st.info(f"No {title} available")
        return

    preferred = [
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
    ]

    cols = [c for c in preferred if c in df.columns]

    if not cols:
        cols = list(df.columns)

    st.dataframe(
        df[cols].head(25),
        use_container_width=True,
        hide_index=True,
    )


def show_market_overview():

    st.header("NTIS EOD MARKET OVERVIEW")

    df = load_dataset("ranking")

    if df is None or df.empty:
        st.warning("Ranking dataset not available.")
        return

    signal_col = _first_available(
        df,
        [
            "Trade View",
            "Signal",
            "Final Signal",
            "Trade Bias",
            "Validation Signal",
        ],
    )

    if signal_col:
        df["Trade View"] = df[signal_col].apply(map_signal)
    else:
        df["Trade View"] = "HOLD"

    show_cards(df)

    info = get_dataset_info("ranking")

    if info.get("available"):
        st.caption(
            f"Last Updated : {info.get('updated')}"
        )

    buy_df = df[df["Trade View"] == "BUY"]

    sell_df = df[df["Trade View"] == "SELL"]

    c1, c2 = st.columns(2)

    with c1:
        _display_table(
            buy_df,
            "BUY Opportunities",
        )

    with c2:
        _display_table(
            sell_df,
            "SELL Opportunities",
        )