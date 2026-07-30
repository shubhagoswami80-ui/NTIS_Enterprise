import streamlit as st
import pandas as pd


def _count_signal(df: pd.DataFrame, signal: str) -> int:
    """Safely count BUY/SELL signals."""
    for column in (
        "Final Signal",
        "Signal",
        "Trade Bias",
        "Validation Signal",
    ):
        if column in df.columns:
            return int(
                (
                    df[column]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .eq(signal.upper())
                ).sum()
            )
    return 0


def _average_score(df: pd.DataFrame) -> float:
    """Return average score from the first available score column."""
    for column in (
        "NTIS Score",
        "NTIS Intraday Score",
        "Validation Score",
    ):
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce").dropna()
            if len(values):
                return round(values.mean(), 2)
    return 0.0


def _high_confidence(df: pd.DataFrame) -> int:
    """Count HIGH confidence records."""
    if "Confidence" not in df.columns:
        return 0

    return int(
        df["Confidence"]
        .fillna("")
        .astype(str)
        .str.upper()
        .eq("HIGH")
        .sum()
    )


def show_cards(df: pd.DataFrame):

    if df is None or df.empty:
        st.warning("No dashboard data available.")
        return

    total = len(df)
    buy = _count_signal(df, "BUY")
    sell = _count_signal(df, "SELL")
    avg_score = _average_score(df)
    high_conf = _high_confidence(df)

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Stocks", f"{total:,}")
    c2.metric("BUY", buy)
    c3.metric("SELL", sell)
    c4.metric("Avg Score", avg_score)
    c5.metric("High Confidence", high_conf)