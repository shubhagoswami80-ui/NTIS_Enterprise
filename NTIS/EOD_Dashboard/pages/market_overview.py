import streamlit as st
import pandas as pd

from EOD_Dashboard.components.dashboard_cards import show_cards
from EOD_Dashboard.components.intelligence_table import render_intelligence_table
from EOD_Dashboard.data.data_loader import get_dataset_info
from EOD_Dashboard.data.intelligence_builder import (
    build_intelligence_view,
    filter_buy_candidates,
    filter_sell_candidates,
)

SIGNAL_COLUMNS = (
    "Trade View",
    "Signal",
    "Final Signal",
    "Trade Bias",
    "Validation Signal",
)

PREFERRED_COLUMNS = (
    "Rank",
    "Symbol",
    "Signal",
    "BUY Probability %",
    "SELL Probability %",
    "Probability",
    "Confidence",
    "Validation Score",
    "Pattern",
    "Pattern Reason",
    "Outcome",
    "Entry Close",
    "Support Strike",
    "Resistance Strike",
)


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


def _average_column(df, column):
    if column not in df.columns:
        return None

    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return None

    return round(values.mean(), 2)


def _top_candidates(df, title, signal):
    if df.empty:
        st.info(f"No {title.lower()} available.")
        return

    st.subheader(title)

    preferred = [
        "Rank",
        "Symbol",
        "BUY Probability %",
        "SELL Probability %",
        "Confidence",
        "Validation Score",
        "Pattern",
        "Pattern Reason",
        "Outcome",
    ]

    columns = [c for c in preferred if c in df.columns]
    if not columns:
        columns = list(df.columns)

    sort_col = "BUY Probability %" if signal == "BUY" else "SELL Probability %"
    if sort_col not in df.columns:
        sort_col = columns[0] if columns else None

    if sort_col is not None:
        display_df = df.sort_values(by=sort_col, ascending=False)
    else:
        display_df = df

    st.dataframe(
        display_df.head(10)[columns],
        use_container_width=True,
        hide_index=True,
    )


def show_market_overview():
    st.header("NTIS EOD EXECUTIVE DASHBOARD")

    intelligence = build_intelligence_view()

    if intelligence is None or intelligence.empty:
        st.warning("Executive intelligence dataset not available.")
        return

    signal_col = _first_available(intelligence, SIGNAL_COLUMNS)
    if signal_col:
        intelligence["Trade View"] = intelligence[signal_col].apply(map_signal)
    else:
        intelligence["Trade View"] = "HOLD"

    show_cards(intelligence)

    dataset_info = get_dataset_info("ranking") or {}
    if dataset_info.get("available"):
        st.caption(f"Last Updated : {dataset_info.get('updated')}")

    buy_df = filter_buy_candidates(intelligence)
    sell_df = filter_sell_candidates(intelligence)

    avg_buy_prob = _average_column(buy_df, "BUY Probability %")
    avg_sell_prob = _average_column(sell_df, "SELL Probability %")
    avg_validation = _average_column(intelligence, "Validation Score")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("BUY Opportunities", f"{len(buy_df):,}")
    with col2:
        st.metric("SELL Opportunities", f"{len(sell_df):,}")
    with col3:
        st.metric(
            "Avg Validation Score",
            f"{avg_validation if avg_validation is not None else 'N/A'}",
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric(
            "Avg BUY Probability",
            f"{avg_buy_prob if avg_buy_prob is not None else 'N/A'}%",
        )
    with col5:
        st.metric(
            "Avg SELL Probability",
            f"{avg_sell_prob if avg_sell_prob is not None else 'N/A'}%",
        )
    with col6:
        st.metric(
            "High Confidence",
            int(
                intelligence["Confidence"].fillna("")
                .astype(str)
                .str.upper()
                .eq("HIGH")
                .sum()
            ) if "Confidence" in intelligence.columns else "N/A",
        )

    st.divider()

    left_col, right_col = st.columns(2)
    with left_col:
        _top_candidates(buy_df, "Top BUY Candidates", "BUY")
    with right_col:
        _top_candidates(sell_df, "Top SELL Candidates", "SELL")

    st.divider()
    st.subheader("Executive Candidate Ranking")

    render_intelligence_table(
        dataframe=intelligence,
        title="Executive Candidate Ranking",
        preferred_columns=PREFERRED_COLUMNS,
        updated=dataset_info.get("updated"),
        filename="executive_dashboard.csv",
    )
