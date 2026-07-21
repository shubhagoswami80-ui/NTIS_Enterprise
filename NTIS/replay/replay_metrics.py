"""
=========================================================
NTIS Replay Metrics
Version : 1.0
Purpose :
    Calculate replay performance metrics
=========================================================
"""

import pandas as pd


class ReplayMetrics:

    @staticmethod
    def total_trades(df):
        return len(df)

    @staticmethod
    def winning_trades(df):
        return len(df[df["success"] == True])

    @staticmethod
    def losing_trades(df):
        return len(df[df["success"] == False])

    @staticmethod
    def accuracy(df):

        total = ReplayMetrics.total_trades(df)

        if total == 0:
            return 0.0

        return round(
            ReplayMetrics.winning_trades(df) / total * 100,
            2,
        )

    @staticmethod
    def average_pnl(df):

        if df.empty:
            return 0.0

        return round(df["pnl"].mean(), 2)

    @staticmethod
    def gross_profit(df):

        if df.empty:
            return 0.0

        return round(
            df[df["pnl"] > 0]["pnl"].sum(),
            2,
        )

    @staticmethod
    def gross_loss(df):

        if df.empty:
            return 0.0

        return round(
            df[df["pnl"] < 0]["pnl"].sum(),
            2,
        )

    @staticmethod
    def max_profit(df):

        if df.empty:
            return 0.0

        return round(df["pnl"].max(), 2)

    @staticmethod
    def max_loss(df):

        if df.empty:
            return 0.0

        return round(df["pnl"].min(), 2)