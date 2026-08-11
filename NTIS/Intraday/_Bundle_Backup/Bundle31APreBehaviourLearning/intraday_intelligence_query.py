"""
===========================================================
NTIS Intraday Intelligence Query

Purpose:
    Query historical intelligence loaded from learning memory
    or pattern_statistics.csv.
===========================================================
"""

import pandas as pd


class IntradayIntelligenceQuery:

    def __init__(self, loader):

        self.loader = loader
        self.df = loader.get_dataframe()

        self.pattern_index = loader.get_pattern_index()
        self.symbol_index = loader.get_symbol_index()

    # --------------------------------------------------------------

    def by_pattern_id(self, pattern_id):

        if pattern_id not in self.pattern_index:
            return pd.DataFrame()

        return self.df.iloc[
            self.pattern_index[pattern_id]
        ].copy()

    # --------------------------------------------------------------

    def by_pattern_dna(self, pattern_dna):

        if self.df.empty or "Pattern_DNA" not in self.df.columns:
            return pd.DataFrame()

        return self.df[
            self.df["Pattern_DNA"] == pattern_dna
        ].copy()

    # --------------------------------------------------------------

    def by_symbol(self, symbol):

        if symbol not in self.symbol_index:
            return pd.DataFrame()

        return self.df.iloc[
            self.symbol_index[symbol]
        ].copy()

    # --------------------------------------------------------------

    @staticmethod
    def _numeric_total(df, column, default=0):

        if column not in df.columns:
            return default

        return pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).sum()

    # --------------------------------------------------------------

    def _statistics_summary(self, history):

        occurrences = self._numeric_total(
            history,
            "Occurrences",
            len(history),
        )

        wins = self._numeric_total(
            history,
            "Successful_Trades",
        )

        losses = self._numeric_total(
            history,
            "Failed_Trades",
        )

        return {

            "Occurrences": int(occurrences),

            "Wins": int(wins),

            "Losses": int(losses),

            "WinRate": round(
                wins * 100 / occurrences,
                2,
            ) if occurrences else 0,

            "AveragePnL": 0,

        }

    # --------------------------------------------------------------

    def historical_summary(self, pattern_id):

        history = self.by_pattern_id(pattern_id)

        if history.empty:

            return {

                "Occurrences": 0,

                "Wins": 0,

                "Losses": 0,

                "WinRate": 0,

                "AveragePnL": 0,

            }

        if {
            "Occurrences",
            "Successful_Trades",
            "Failed_Trades",
        }.issubset(history.columns):
            return self._statistics_summary(history)

        wins = history[
            history["Outcome"] == "WIN"
        ]

        losses = history[
            history["Outcome"] == "LOSS"
        ]

        pnl = pd.to_numeric(
            history["PnL"],
            errors="coerce"
        ).fillna(0)

        return {

            "Occurrences": len(history),

            "Wins": len(wins),

            "Losses": len(losses),

            "WinRate": round(
                len(wins) * 100 / len(history),
                2
            ),

            "AveragePnL": round(
                pnl.mean(),
                2
            )

        }

    # --------------------------------------------------------------

    def latest_match(self, pattern_id):

        history = self.by_pattern_id(pattern_id)

        if history.empty:
            return None

        return history.iloc[-1].to_dict()
