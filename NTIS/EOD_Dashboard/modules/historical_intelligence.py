"""
NTIS Dashboard - Historical Intelligence
Bundle 1A

Production entry point:
    build_historical_intelligence(df)

This module converts a historical snapshot DataFrame into
dashboard-ready intelligence datasets.
"""

from __future__ import annotations
import pandas as pd


_NUMERIC = [
    "NTIS Score","Probability","Price","Support","Resistance",
    "Price Chg %","OI Chg %","PCR"
]


def _to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in _NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def build_historical_intelligence(df: pd.DataFrame) -> dict:
    df = _to_numeric(df)

    trade_col = "Trade Bias" if "Trade Bias" in df.columns else None
    prob_col = "Probability" if "Probability" in df.columns else None

    summary = {
        "total_stocks": len(df),
        "buy_count": int((df[trade_col] == "BUY").sum()) if trade_col else 0,
        "sell_count": int((df[trade_col] == "SELL").sum()) if trade_col else 0,
        "avg_score": round(df["NTIS Score"].mean(),2) if "NTIS Score" in df else 0,
        "highest_score": round(df["NTIS Score"].max(),2) if "NTIS Score" in df else 0,
        "lowest_score": round(df["NTIS Score"].min(),2) if "NTIS Score" in df else 0,
    }

    buy = df.copy()
    if trade_col:
        buy = buy[buy[trade_col] == "BUY"]
    if prob_col:
        buy = buy[buy[prob_col] >= 70]
    if {"Probability","NTIS Score"}.issubset(buy.columns):
        buy = buy.sort_values(["Probability","NTIS Score"], ascending=False)

    sell = df.copy()
    if trade_col:
        sell = sell[sell[trade_col] == "SELL"]
    if prob_col:
        sell = sell[sell[prob_col] >= 70]
    if {"Probability","NTIS Score"}.issubset(sell.columns):
        sell = sell.sort_values(["Probability","NTIS Score"], ascending=False)

    ranking = df.sort_values("NTIS Score", ascending=False) if "NTIS Score" in df.columns else df

    support = df.copy()
    if {"Price","Support"}.issubset(support.columns):
        support["Distance to Support %"] = ((support["Price"]-support["Support"])/support["Price"]*100).round(2)
    if {"Price","Resistance"}.issubset(support.columns):
        support["Distance to Resistance %"] = ((support["Resistance"]-support["Price"])/support["Price"]*100).round(2)

    if "Pattern" in df.columns:
        pattern = (
            df.groupby("Pattern", dropna=False)
              .agg(Count=("Pattern","size"),
                   **({"Average Probability":("Probability","mean")} if "Probability" in df.columns else {}),
                   **({"Average NTIS Score":("NTIS Score","mean")} if "NTIS Score" in df.columns else {}))
              .reset_index()
        )
    else:
        pattern = pd.DataFrame()

    return {
        "summary": summary,
        "buy_df": buy,
        "sell_df": sell,
        "ranking_df": ranking,
        "support_df": support,
        "pattern_df": pattern,
    }
