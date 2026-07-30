"""
NTIS Dashboard - Market Breadth
Production Version
"""
from __future__ import annotations

import pandas as pd


def _first_available(df: pd.DataFrame, columns):

    for column in columns:
        if column in df.columns:
            return df[column].fillna("").astype(str)

    return pd.Series(dtype=str)


def calculate_market_breadth(df: pd.DataFrame) -> dict:

    total = len(df)

    trade = _first_available(
        df,
        [
            "Trade Bias",
            "Final Signal",
            "Signal",
            "Validation Signal",
            "Trade View",
        ],
    ).str.upper()

    pattern = _first_available(
        df,
        [
            "Pattern",
            "Detected Pattern",
        ],
    )

    confidence = _first_available(
        df,
        [
            "Confidence",
        ],
    ).str.upper()

    buy = int(trade.eq("BUY").sum())
    sell = int(trade.eq("SELL").sum())
    hold = max(total - buy - sell, 0)

    bullish = int(
        pattern.str.contains(
            "LONG|BULL",
            case=False,
            na=False,
        ).sum()
    )

    bearish = int(
        pattern.str.contains(
            "SHORT|BEAR",
            case=False,
            na=False,
        ).sum()
    )

    high_conf = int(confidence.eq("HIGH").sum())

    def pct(value):

        if total == 0:
            return 0.0

        return round(value * 100 / total, 2)

    return {

        "Total Stocks": total,

        "BUY": buy,
        "SELL": sell,
        "HOLD": hold,

        "BUY %": pct(buy),
        "SELL %": pct(sell),
        "HOLD %": pct(hold),

        "Bullish Patterns": bullish,
        "Bearish Patterns": bearish,

        "High Confidence": high_conf,
    }