"""
=========================================================
NTIS Replay Filters
Version : 1.0
Purpose :
    Filter Replay Results for analysis
=========================================================
"""

import pandas as pd


class ReplayFilters:

    @staticmethod
    def winners(df):

        if df.empty:
            return pd.DataFrame()

        return df[df["success"] == True].copy()

    @staticmethod
    def losers(df):

        if df.empty:
            return pd.DataFrame()

        return df[df["success"] == False].copy()

    @staticmethod
    def probability(df, minimum=80):

        if df.empty:
            return pd.DataFrame()

        return df[df["probability"] >= minimum].copy()

    @staticmethod
    def pattern(df, pattern):

        if df.empty:
            return pd.DataFrame()

        return df[df["pattern"] == pattern].copy()

    @staticmethod
    def symbol(df, symbol):

        if df.empty:
            return pd.DataFrame()

        return df[df["symbol"] == symbol].copy()

    @staticmethod
    def trade_bias(df, bias):

        if df.empty:
            return pd.DataFrame()

        return df[df["trade_bias"] == bias].copy()