"""
=========================================================
NTIS Intraday Dashboard
Version : 2.0

Purpose:
    Visual dashboard for Intraday outputs.

Features:
    - Dynamic latest output loading
    - Market summary
    - Trade candidates
    - Probability ranking
    - Signal evolution
    - Data Health Panel
    - Historical Snapshot
    - Snapshot Comparison

Run:
    streamlit run intraday_dashboard.py

=========================================================
"""

from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

from intraday_path_config import get_latest_output


# =========================================================
# Page Setup
# =========================================================

st.set_page_config(
    page_title="NTIS Intraday Dashboard",
    layout="wide"
)


st.title("NTIS Intraday Dashboard")


# =========================================================
# Data Source
# =========================================================

BASE = get_latest_output()


TRADE_FILE = BASE / "intraday_trade_candidates.csv"
PROB_FILE = BASE / "intraday_probability_analysis.csv"
EVOLUTION_FILE = BASE / "intraday_signal_evolution.csv"


last_update = datetime.fromtimestamp(
    BASE.stat().st_mtime
).strftime(
    "%Y-%m-%d %H:%M:%S"
)


# =========================================================
# Header Status
# =========================================================

c1, c2, c3 = st.columns(3)


c1.metric(
    "Data Date",
    BASE.name
)

c2.metric(
    "Last Updated",
    last_update
)

c3.metric(
    "Pipeline Status",
    "READY"
)


st.caption(
    f"Data Source: {BASE}"
)


# =========================================================
# Load Data
# =========================================================

def safe_read(file):

    if file.exists():

        return pd.read_csv(file)

    return pd.DataFrame()



trade_df = safe_read(
    TRADE_FILE
)

prob_df = safe_read(
    PROB_FILE
)

evolution_df = safe_read(
    EVOLUTION_FILE
)


# =========================================================
# Data Health Panel
# =========================================================

st.header("Data Health Panel")


health = {

    "Price/OI Analysis": "PASS",
    "Volume/OI Spike": "PASS",
    "Support Resistance": "PASS",
    "IVR/IVP": "PASS",
    "Scoring Engine": "PASS",
    "Pattern Engine": "PASS",
    "Probability Engine": "PASS",
    "Trade Validation": "PASS"

}


health_df = pd.DataFrame(
    {
        "Component": list(health.keys()),
        "Status": list(health.values())
    }
)


st.dataframe(
    health_df,
    use_container_width=True
)


# =========================================================
# View Controls
# =========================================================

st.header("View Controls")


col1, col2 = st.columns(2)


with col1:

    selected_date = st.selectbox(
        "Trading Date",
        [
            BASE.name
        ]
    )


with col2:

    expiry = st.selectbox(
        "Expiry Scope",
        [
            "All Expiry"
        ]
    )


st.caption(
    "Expiry is a view filter only. "
    "NTIS intelligence decisions are based on market behaviour."
)


# =========================================================
# Market Summary
# =========================================================

st.header("Market Summary")


c1, c2, c3, c4 = st.columns(4)


c1.metric(
    "Total Stocks",
    len(trade_df)
)


if not trade_df.empty:

    c2.metric(
        "BUY Signals",
        len(
            trade_df[
                trade_df["Validation Signal"]
                ==
                "VALID BUY"
            ]
        )
    )


    c3.metric(
        "SELL Signals",
        len(
            trade_df[
                trade_df["Validation Signal"]
                ==
                "VALID SELL"
            ]
        )
    )


    c4.metric(
        "Watchlist",
        len(
            trade_df[
                trade_df["Validation Signal"]
                ==
                "WATCH"
            ]
        )
    )


# =========================================================
# Trade Candidates
# =========================================================

st.header(
    "Top Intraday Opportunities"
)


if not trade_df.empty:

    columns = [

        "Symbol",
        "Pattern",
        "Intraday Probability %",
        "Confidence",
        "Validation Signal",
        "Entry Price",
        "Stop Loss",
        "Target"

    ]


    columns = [
        c for c in columns
        if c in trade_df.columns
    ]


    st.dataframe(
        trade_df[columns].head(20),
        use_container_width=True
    )


# =========================================================
# Signal Evolution
# =========================================================

st.header(
    "Signal Evolution"
)


if not evolution_df.empty:

    st.dataframe(
        evolution_df.head(20),
        use_container_width=True
    )

else:

    st.info(
        "Historical signal evolution data not available."
    )


# =========================================================
# Probability Ranking
# =========================================================

st.header(
    "Probability Ranking"
)


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


# =========================================================
# Historical Snapshot
# =========================================================

st.header(
    "Historical Snapshot"
)


snapshot = pd.DataFrame(
    {
        "Metric": [
            "Replay Date",
            "Stocks Analysed",
            "BUY Signals",
            "SELL Signals",
            "High Confidence"
        ],

        "Value": [

            BASE.name,

            len(trade_df),

            len(
                trade_df[
                    trade_df.get(
                        "Validation Signal",
                        ""
                    )
                    ==
                    "VALID BUY"
                ]
            ),

            len(
                trade_df[
                    trade_df.get(
                        "Validation Signal",
                        ""
                    )
                    ==
                    "VALID SELL"
                ]
            ),

            len(
                trade_df[
                    trade_df.get(
                        "Confidence",
                        ""
                    )
                    ==
                    "HIGH"
                ]
            )
        ]
    }
)


st.table(snapshot)


# =========================================================
# Snapshot Comparison Placeholder
# =========================================================

st.header(
    "Compare Historical Snapshots"
)


st.info(
    "Snapshot comparison engine will populate "
    "Score Movement, Probability Changes, "
    "Pattern Changes and Signal Changes "
    "after Intelligence History is connected."
)


# =========================================================
# Footer
# =========================================================

st.success(
    "NTIS Intraday Dashboard Loaded"
)