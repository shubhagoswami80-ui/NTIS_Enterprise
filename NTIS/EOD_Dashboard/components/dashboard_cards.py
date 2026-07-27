import streamlit as st


def show_cards(df):

    total = len(df)

    buy = 0
    sell = 0
    avg_score = 0

    if "Signal" in df.columns:
        buy = int((df["Signal"].astype(str).str.upper() == "BUY").sum())
        sell = int((df["Signal"].astype(str).str.upper() == "SELL").sum())

    if "NTIS Score" in df.columns:
        avg_score = round(df["NTIS Score"].mean(), 2)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Stocks", total)
    c2.metric("BUY Signals", buy)
    c3.metric("SELL Signals", sell)
    c4.metric("Avg NTIS Score", avg_score)
