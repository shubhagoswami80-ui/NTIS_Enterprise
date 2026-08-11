
"""
=========================================================
NTIS Intraday Dashboard
Version : 2.1

Update:
    - Added latest snapshot resolver
    - Holiday/weekend fallback support
    - Missing data service message

=========================================================
"""

from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

from intraday_path_config import get_latest_output
from intraday_latest_snapshot_resolver import IntradayLatestSnapshotResolver


st.set_page_config(
    page_title="NTIS Intraday Dashboard",
    layout="wide"
)


st.title("NTIS Intraday Dashboard")


# =========================================================
# Latest Snapshot Resolver
# =========================================================

OUTPUT_ROOT = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output"
)

resolver = IntradayLatestSnapshotResolver(
    OUTPUT_ROOT
)

BASE = resolver.get_latest_snapshot()


if BASE is None:

    st.error(
        "🔴 Service Issue\n\n"
        "No Intraday intelligence snapshot available."
    )

    st.stop()


if BASE.name != datetime.today().strftime("%Y-%m-%d"):

    st.warning(
        f"🟡 No new market data available today.\n\n"
        f"Showing latest intelligence snapshot:\n"
        f"{BASE.name}"
    )


st.caption(
    f"Data Source: {BASE}"
)


TRADE_FILE = BASE / "intraday_trade_candidates.csv"
PROB_FILE = BASE / "intraday_probability_analysis.csv"
EVOLUTION_FILE = BASE / "intraday_signal_evolution.csv"


def safe_read(file):

    if file.exists():
        return pd.read_csv(file)

    return pd.DataFrame()


trade_df = safe_read(TRADE_FILE)
prob_df = safe_read(PROB_FILE)
evolution_df = safe_read(EVOLUTION_FILE)


# Existing dashboard sections retained

st.header("Market Summary")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Stocks", len(trade_df))

if not trade_df.empty:

    c2.metric(
        "BUY Signals",
        len(trade_df[
            trade_df["Validation Signal"] == "VALID BUY"
        ])
    )

    c3.metric(
        "SELL Signals",
        len(trade_df[
            trade_df["Validation Signal"] == "VALID SELL"
        ])
    )

    c4.metric(
        "Watchlist",
        len(trade_df[
            trade_df["Validation Signal"] == "WATCH"
        ])
    )


st.header("Top Intraday Opportunities")

if not trade_df.empty:

    cols = [
        "Symbol",
        "Pattern",
        "Intraday Probability %",
        "Confidence",
        "Validation Signal",
        "Entry Price",
        "Stop Loss",
        "Target"
    ]

    cols = [
        c for c in cols
        if c in trade_df.columns
    ]

    st.dataframe(
        trade_df[cols].head(20),
        use_container_width=True
    )


st.header("Signal Evolution")

if not evolution_df.empty:

    st.dataframe(
        evolution_df.head(20),
        use_container_width=True
    )


st.header("Probability Ranking")

if (
    not prob_df.empty
    and "Symbol" in prob_df.columns
    and "Intraday Probability %" in prob_df.columns
):

    st.bar_chart(
        prob_df.set_index("Symbol")
        ["Intraday Probability %"]
        .head(20)
    )


st.success(
    "NTIS Intraday Dashboard Loaded"
)
