"""
NTIS Intraday Dashboard
Version : 2.2

Resolver v2 integration:
- Snapshot date visibility
- LIVE / PROCESSING_REQUIRED / FALLBACK status
- Existing dashboard sections preserved
"""

from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

from intraday_latest_snapshot_resolver import IntradayLatestSnapshotResolver


st.set_page_config(page_title="NTIS Intraday Dashboard", layout="wide")

st.title("NTIS Intraday Dashboard")

OUTPUT_ROOT = Path(r"E:\NSE_Daily_Analysis\Intraday\Output\2026\July")
SOURCE_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot\july26")

requested_date = datetime.today().strftime("%Y-%m-%d")

resolver = IntradayLatestSnapshotResolver(
    SOURCE_ROOT,
    OUTPUT_ROOT
)

status = resolver.resolve(requested_date)

st.header("Snapshot Status")

c1, c2, c3 = st.columns(3)

c1.metric("Requested Date", requested_date)
c2.metric("Status", status["status"])
c3.metric("Snapshot Date", status["snapshot_date"] or "None")

st.info(status["reason"])

if status["status"] in ["LIVE", "FALLBACK"]:
    BASE = OUTPUT_ROOT / status["snapshot_date"]
elif status["status"] == "PROCESSING_REQUIRED":
    st.warning("Source data exists but intelligence snapshot is pending.")
    st.stop()
else:
    st.error("No valid intraday snapshot available.")
    st.stop()

st.caption(f"Data Source: {BASE}")

def safe_read(file):
    return pd.read_csv(file) if file.exists() else pd.DataFrame()

trade_df = safe_read(BASE / "intraday_trade_candidates.csv")
prob_df = safe_read(BASE / "intraday_probability_analysis.csv")
evolution_df = safe_read(BASE / "intraday_signal_evolution.csv")

st.header("Market Summary")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Stocks", len(trade_df))

if not trade_df.empty:
    c2.metric("BUY Signals", len(trade_df[trade_df["Validation Signal"] == "VALID BUY"]))
    c3.metric("SELL Signals", len(trade_df[trade_df["Validation Signal"] == "VALID SELL"]))
    c4.metric("Watchlist", len(trade_df[trade_df["Validation Signal"] == "WATCH"]))

st.header("Top Intraday Opportunities")

if not trade_df.empty:
    cols = [
        c for c in [
            "Symbol","Pattern","Intraday Probability %",
            "Confidence","Validation Signal",
            "Entry Price","Stop Loss","Target"
        ]
        if c in trade_df.columns
    ]
    st.dataframe(trade_df[cols].head(20), use_container_width=True)

st.header("Signal Evolution")

if not evolution_df.empty:
    st.dataframe(evolution_df.head(20), use_container_width=True)

st.header("Probability Ranking")

if not prob_df.empty and "Symbol" in prob_df.columns and "Intraday Probability %" in prob_df.columns:
    st.bar_chart(prob_df.set_index("Symbol")["Intraday Probability %"].head(20))

st.success("NTIS Intraday Dashboard Loaded")
