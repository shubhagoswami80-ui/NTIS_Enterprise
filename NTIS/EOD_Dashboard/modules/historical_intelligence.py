"""
NTIS Dashboard - Historical Intelligence
Production Version
"""

from __future__ import annotations

import pandas as pd

_NUMERIC = (
    "NTIS Score",
    "Probability",
    "BUY Probability %",
    "Price",
    "CMP",
    "Support",
    "Resistance",
    "Price Chg %",
    "OI Chg %",
    "PCR",
)


def _to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in _NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _first(df, columns):
    for c in columns:
        if c in df.columns:
            return c
    return None


def build_historical_intelligence(df: pd.DataFrame) -> dict:

    if df is None:
        df = pd.DataFrame()

    df = _to_numeric(df)

    trade_col = _first(
        df,
        (
            "Trade Bias",
            "Final Signal",
            "Signal",
            "Validation Signal",
            "Trade View",
        ),
    )

    prob_col = _first(
        df,
        (
            "Probability",
            "BUY Probability %",
        ),
    )

    score_col = _first(
        df,
        (
            "NTIS Score",
            "NTIS Intraday Score",
        ),
    )

    summary = {
        "total_stocks": len(df),
        "buy_count": 0,
        "sell_count": 0,
        "avg_score": 0,
        "highest_score": 0,
        "lowest_score": 0,
    }

    if trade_col:
        signal = (
            df[trade_col]
            .fillna("")
            .astype(str)
            .str.upper()
        )

        summary["buy_count"] = int(signal.eq("BUY").sum())
        summary["sell_count"] = int(signal.eq("SELL").sum())

    if score_col and not df.empty:
        summary["avg_score"] = round(df[score_col].mean(), 2)
        summary["highest_score"] = round(df[score_col].max(), 2)
        summary["lowest_score"] = round(df[score_col].min(), 2)

    buy = df.copy()

    if trade_col:
        buy = buy[
            buy[trade_col]
            .astype(str)
            .str.upper()
            .eq("BUY")
        ]

    if prob_col:
        buy = buy[buy[prob_col] >= 70]

    if score_col:
        buy = buy.sort_values(
            [prob_col, score_col] if prob_col else [score_col],
            ascending=False,
        )

    sell = df.copy()

    if trade_col:
        sell = sell[
            sell[trade_col]
            .astype(str)
            .str.upper()
            .eq("SELL")
        ]

    if prob_col:
        sell = sell[sell[prob_col] >= 70]

    if score_col:
        sell = sell.sort_values(
            [prob_col, score_col] if prob_col else [score_col],
            ascending=False,
        )

    ranking = (
        df.sort_values(score_col, ascending=False)
        if score_col
        else df
    )

    support = df.copy()

    price_col = _first(df, ("Price", "CMP"))

    if price_col and "Support" in df.columns:
        support["Distance to Support %"] = (
            (support[price_col] - support["Support"])
            / support[price_col]
            * 100
        ).round(2)

    if price_col and "Resistance" in df.columns:
        support["Distance to Resistance %"] = (
            (support["Resistance"] - support[price_col])
            / support[price_col]
            * 100
        ).round(2)

    if "Pattern" in df.columns:
        agg = {"Count": ("Pattern", "size")}

        if prob_col:
            agg["Average Probability"] = (prob_col, "mean")

        if score_col:
            agg["Average NTIS Score"] = (score_col, "mean")

        pattern = (
            df.groupby("Pattern", dropna=False)
            .agg(**agg)
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