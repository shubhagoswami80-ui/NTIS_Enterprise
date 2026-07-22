"""
=========================================================
NTIS Intraday Dashboard
Version : 1.0

Purpose:
    Visual dashboard for Intraday outputs.

Reads:
    intraday_trade_candidates.csv
    intraday_probability_analysis.csv
    intraday_signal_evolution.csv

Technology:
    Streamlit

Run:
    streamlit run intraday_dashboard.py
=========================================================
"""

from pathlib import Path
import pandas as pd
import streamlit as st


BASE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22"
)


TRADE_FILE = BASE / "intraday_trade_candidates.csv"
PROB_FILE = BASE / "intraday_probability_analysis.csv"
EVOLUTION_FILE = BASE / "intraday_signal_evolution.csv"


st.set_page_config(
    page_title="NTIS Intraday Dashboard",
    layout="wide"
)


st.title("NTIS Intraday Dashboard")


# Load files

trade_df = pd.read_csv(
    TRADE_FILE
)

prob_df = pd.read_csv(
    PROB_FILE
)

evolution_df = pd.read_csv(
    EVOLUTION_FILE
)


# Summary

st.header("Market Summary")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Stocks",
    len(trade_df)
)

c2.metric(
    "BUY Signals",
    len(
        trade_df[
            trade_df["Validation Signal"]
            == "VALID BUY"
        ]
    )
)

c3.metric(
    "SELL Signals",
    len(
        trade_df[
            trade_df["Validation Signal"]
            == "VALID SELL"
        ]
    )
)

c4.metric(
    "Watchlist",
    len(
        trade_df[
            trade_df["Validation Signal"]
            == "WATCH"
        ]
    )
)


# Top candidates

st.header("Top Intraday Opportunities")

show = trade_df[
    [
        "Symbol",
        "Pattern",
        "Intraday Probability %",
        "Confidence",
        "Validation Signal",
        "Entry Price",
        "Stop Loss",
        "Target"
    ]
].head(20)


st.dataframe(
    show,
    use_container_width=True
)


# Evolution

st.header("Signal Evolution")

st.dataframe(
    evolution_df.head(20),
    use_container_width=True
)


# Probability distribution

st.header("Probability Ranking")

st.bar_chart(
    prob_df.set_index("Symbol")
    ["Intraday Probability %"]
    .head(20)
)


st.success(
    "NTIS Intraday Dashboard Loaded"
)
