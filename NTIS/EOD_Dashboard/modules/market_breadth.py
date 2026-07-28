"""
NTIS Dashboard - Market Breadth
"""
from __future__ import annotations
import pandas as pd

def calculate_market_breadth(df: pd.DataFrame) -> dict:
    total = len(df)
    trade = df["Trade Bias"] if "Trade Bias" in df.columns else pd.Series(dtype=str)
    patt = df["Pattern"] if "Pattern" in df.columns else pd.Series(dtype=str)

    buy = int((trade == "BUY").sum())
    sell = int((trade == "SELL").sum())
    neutral = max(total - buy - sell, 0)

    bullish = int(patt.astype(str).str.contains("Long|Bull", case=False, na=False).sum())
    bearish = int(patt.astype(str).str.contains("Short|Bear", case=False, na=False).sum())

    pct = lambda x: round((x / total) * 100, 2) if total else 0

    return {
        "Total Stocks": total,
        "BUY": buy,
        "SELL": sell,
        "Neutral": neutral,
        "Bullish Patterns": bullish,
        "Bearish Patterns": bearish,
        "BUY %": pct(buy),
        "SELL %": pct(sell),
        "Neutral %": pct(neutral),
    }
