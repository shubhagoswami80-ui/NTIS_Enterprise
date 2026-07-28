"""
HMME V1.7 Feature Engine

Purpose:
Create additional EOD intelligence features
from existing NTIS OHLC reports.

Features:
- Daily Range %
- Candle Structure
- Gap %
- Previous High/Low context

ATR placeholder included for future rolling OHLC history.
"""

import pandas as pd


class HMMEFeatureEngineV17:

    def process(self, df):

        if df.empty:
            return df

        df = df.copy()

        numeric_cols = [
            "Open",
            "High",
            "Low",
            "Close"
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

        # Daily Range %
        if all(c in df.columns for c in ["High", "Low", "Close"]):
            df["Daily Range %"] = (
                (df["High"] - df["Low"])
                / df["Close"]
                * 100
            )

        # Candle Body %
        if all(c in df.columns for c in ["Open", "Close", "High", "Low"]):
            candle_range = df["High"] - df["Low"]

            df["Candle Body %"] = (
                abs(df["Close"] - df["Open"])
                / candle_range.replace(0, 1)
                * 100
            )

            df["Candle Type"] = "NEUTRAL"

            df.loc[
                df["Close"] > df["Open"],
                "Candle Type"
            ] = "BULLISH"

            df.loc[
                df["Close"] < df["Open"],
                "Candle Type"
            ] = "BEARISH"

        # Gap %
        if "Open" in df.columns:
            if "Previous Close" in df.columns:
                df["Gap %"] = (
                    (df["Open"] - df["Previous Close"])
                    / df["Previous Close"]
                    * 100
                )

        # ATR placeholder
        if "ATR 14" not in df.columns:
            df["ATR 14"] = None

        return df
