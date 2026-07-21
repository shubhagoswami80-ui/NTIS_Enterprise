"""
=========================================================
NTIS Replay Validator
Version : 1.0
Purpose :
    Validate Replay Results
=========================================================
"""

import pandas as pd


class ReplayValidator:

    def __init__(self):
        pass

    @staticmethod
    def validate(df):

        if df.empty:
            return {
                "Total Trades": 0,
                "Wins": 0,
                "Losses": 0,
                "Accuracy": 0.0,
            }

        total = len(df)

        wins = len(df[df["success"] == True])

        losses = total - wins

        accuracy = round((wins / total) * 100, 2)

        return {
            "Total Trades": total,
            "Wins": wins,
            "Losses": losses,
            "Accuracy": accuracy,
        }

    @staticmethod
    def calculate_statistics(df):

        if df.empty:
            return pd.DataFrame()

        stats = {
            "Total Trades": len(df),
            "Winning Trades": len(df[df["success"]]),
            "Losing Trades": len(df[~df["success"]]),
            "Average PnL": round(df["pnl"].mean(), 2),
            "Maximum Profit": round(df["pnl"].max(), 2),
            "Maximum Loss": round(df["pnl"].min(), 2),
        }

        return pd.DataFrame([stats])