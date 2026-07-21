"""
=========================================================
NTIS Replay Analyzer
Version : 1.0
Purpose :
    Analyze Historical Replay Results
=========================================================
"""

import pandas as pd


class ReplayAnalyzer:

    @staticmethod
    def by_symbol(df):

        if df.empty:
            return pd.DataFrame()

        return (
            df.groupby("symbol")
            .agg(
                Trades=("symbol", "count"),
                Wins=("success", "sum"),
                AveragePnL=("pnl", "mean"),
                TotalPnL=("pnl", "sum"),
            )
            .reset_index()
        )

    @staticmethod
    def by_probability(df):

        if df.empty:
            return pd.DataFrame()

        bins = [0, 50, 60, 70, 80, 90, 100]

        labels = [
            "0-50",
            "51-60",
            "61-70",
            "71-80",
            "81-90",
            "91-100",
        ]

        temp = df.copy()

        temp["Probability Band"] = pd.cut(
            temp["probability"],
            bins=bins,
            labels=labels,
            include_lowest=True,
        )

        return (
            temp.groupby("Probability Band")
            .agg(
                Trades=("Probability Band", "count"),
                Wins=("success", "sum"),
                AveragePnL=("pnl", "mean"),
            )
            .reset_index()
        )

    @staticmethod
    def by_pattern(df):

        if df.empty:
            return pd.DataFrame()

        return (
            df.groupby("pattern")
            .agg(
                Trades=("pattern", "count"),
                Wins=("success", "sum"),
                AveragePnL=("pnl", "mean"),
            )
            .reset_index()
        )