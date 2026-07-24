"""
HMME V1.7 EOD Feature Builder V2

Fixes:
- Sort by Symbol + Report_Date
- Reliable Previous Close
- Stable ATR14 calculation
- Multi-day / multi-month history support
"""

import pandas as pd


class HMMEEODFeatureBuilderV17:

    def build(self, df):

        if df.empty:
            return df

        df = df.copy()

        df.columns = [str(c).strip() for c in df.columns]

        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

        if "Symbol" not in df.columns:
            return pd.DataFrame()

        if "Report_Date" not in df.columns:
            return pd.DataFrame()

        df["Report_Date"] = pd.to_datetime(
            df["Report_Date"],
            errors="coerce"
        )

        df = df.sort_values(
            ["Symbol", "Report_Date"]
        ).reset_index(drop=True)

        df["Previous Close"] = (
            df.groupby("Symbol")["Close"]
            .shift(1)
        )

        df["Gap %"] = (
            (df["Open"] - df["Previous Close"])
            / df["Previous Close"]
            * 100
        )

        df["Daily Range %"] = (
            (df["High"] - df["Low"])
            / df["Close"]
            * 100
        )

        candle_range = (
            df["High"] - df["Low"]
        ).replace(0, 1)

        df["Candle Body %"] = (
            abs(df["Close"] - df["Open"])
            / candle_range
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

        previous_close = (
            df.groupby("Symbol")["Close"]
            .shift(1)
        )

        true_range = pd.concat(
            [
                df["High"] - df["Low"],
                abs(df["High"] - previous_close),
                abs(df["Low"] - previous_close)
            ],
            axis=1
        ).max(axis=1)

        df["True Range"] = true_range

        df["ATR 14"] = (
            df.groupby("Symbol")["True Range"]
            .rolling(14, min_periods=14)
            .mean()
            .reset_index(level=0, drop=True)
        )

        return df
