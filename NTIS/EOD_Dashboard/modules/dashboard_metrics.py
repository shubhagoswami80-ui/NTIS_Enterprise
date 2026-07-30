"""
NTIS Dashboard - Dashboard Metrics
Enterprise Production Version
"""

from __future__ import annotations

import pandas as pd


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").dropna()


def calculate_dashboard_metrics(df: pd.DataFrame) -> dict:

    metrics = {}

    if df is None or df.empty:
        return metrics

    metrics["Total Stocks"] = int(len(df))

    probability = _numeric(df, "Probability")
    if probability.empty:
        probability = _numeric(df, "BUY Probability %")
    if probability.empty:
        probability = _numeric(df, "Intraday Probability %")

    if not probability.empty:
        metrics["Average Probability"] = round(probability.mean(), 2)
        metrics["Highest Probability"] = round(probability.max(), 2)
        metrics["Lowest Probability"] = round(probability.min(), 2)

    score = _numeric(df, "NTIS Score")
    if score.empty:
        score = _numeric(df, "NTIS Intraday Score")

    if not score.empty:
        metrics["Average Score"] = round(score.mean(), 2)
        metrics["Median Score"] = round(score.median(), 2)
        metrics["Highest Score"] = round(score.max(), 2)

    if {"Price", "Support"}.issubset(df.columns):
        distance = (
            (df["Price"] - df["Support"])
            / df["Price"]
            * 100
        )
        metrics["Avg Support Distance %"] = round(
            pd.to_numeric(distance, errors="coerce").mean(),
            2,
        )

    if {"Price", "Resistance"}.issubset(df.columns):
        distance = (
            (df["Resistance"] - df["Price"])
            / df["Price"]
            * 100
        )
        metrics["Avg Resistance Distance %"] = round(
            pd.to_numeric(distance, errors="coerce").mean(),
            2,
        )

    if "Confidence" in df.columns:
        confidence = (
            df["Confidence"]
            .fillna("")
            .astype(str)
            .str.upper()
        )

        metrics["High Confidence"] = int(
            confidence.eq("HIGH").sum()
        )

    for column in (
        "Final Signal",
        "Signal",
        "Trade Bias",
        "Validation Signal",
    ):
        if column in df.columns:
            signal = (
                df[column]
                .fillna("")
                .astype(str)
                .str.upper()
            )

            metrics["BUY Signals"] = int(signal.eq("BUY").sum())
            metrics["SELL Signals"] = int(signal.eq("SELL").sum())
            break

    return metrics