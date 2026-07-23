from pathlib import Path
import pandas as pd
import streamlit as st

OUTPUT_ROOT = Path(r"E:\NSE_Daily_Analysis\Intraday\Output")

folders = [f for f in OUTPUT_ROOT.iterdir() if f.is_dir()]
BASE = max(folders, key=lambda x:x.name)

st.set_page_config(page_title="NTIS Intraday Dashboard", layout="wide")

st.title("NTIS Intraday Dashboard")
st.info(f"Analysis Date Loaded: {BASE.name}")

trade_df = pd.read_csv(BASE/"intraday_trade_candidates.csv")
prob_df = pd.read_csv(BASE/"intraday_probability_analysis.csv")
evolution_df = pd.read_csv(BASE/"intraday_signal_evolution.csv")

c1,c2,c3,c4 = st.columns(4)

c1.metric("Total Stocks",len(trade_df))
c2.metric("BUY Signals",len(trade_df[trade_df["Validation Signal"]=="VALID BUY"]))
c3.metric("SELL Signals",len(trade_df[trade_df["Validation Signal"]=="VALID SELL"]))
c4.metric("Watchlist",len(trade_df[trade_df["Validation Signal"]=="WATCH"]))

st.header("Top Intraday Opportunities")
st.dataframe(trade_df.head(20),use_container_width=True)

st.header("Signal Evolution")
st.dataframe(evolution_df.head(20),use_container_width=True)

st.header("Probability Ranking")
st.bar_chart(prob_df.set_index("Symbol")["Intraday Probability %"].head(20))
