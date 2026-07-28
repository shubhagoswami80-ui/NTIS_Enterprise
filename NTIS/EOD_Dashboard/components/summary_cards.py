
import streamlit as st

def show_summary_cards(df):

    total = len(df)

    buy = 0
    sell = 0
    watch = 0

    if "Trade View" in df.columns:
        buy = int((df["Trade View"] == "BUY").sum())
        sell = int((df["Trade View"] == "SELL").sum())
        watch = int((df["Trade View"] == "HOLD").sum())

    c1,c2,c3,c4 = st.columns(4)

    c1.metric("Total Stocks", total)
    c2.metric("BUY", buy)
    c3.metric("SELL", sell)
    c4.metric("Watchlist", watch)
