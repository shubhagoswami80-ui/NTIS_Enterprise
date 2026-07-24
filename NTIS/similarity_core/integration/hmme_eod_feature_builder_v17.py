"""
HMME V1.7 EOD Feature Builder

Prepares EOD history for replay.
Adds:
- Previous Close
- Gap %
- Daily Range %
- Candle Type
- Candle Body %
- ATR14
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
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "Symbol" not in df.columns:
            return pd.DataFrame()

        df = df.sort_values(["Symbol"])

        df["Previous Close"] = (
            df.groupby("Symbol")["Close"].shift(1)
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

        candle_range = (df["High"] - df["Low"]).replace(0, 1)

        df["Candle Body %"] = (
            abs(df["Close"] - df["Open"])
            / candle_range
            * 100
        )

        df["Candle Type"] = "NEUTRAL"
        df.loc[df["Close"] > df["Open"], "Candle Type"] = "BULLISH"
        df.loc[df["Close"] < df["Open"], "Candle Type"] = "BEARISH"

        prev_close = df.groupby("Symbol")["Close"].shift(1)

        tr = pd.concat(
            [
                df["High"] - df["Low"],
                abs(df["High"] - prev_close),
                abs(df["Low"] - prev_close)
            ],
            axis=1
        ).max(axis=1)

        df["ATR 14"] = (
            df.assign(True_Range=tr)
            .groupby("Symbol")["True_Range"]
            .rolling(14)
            .mean()
            .reset_index(level=0, drop=True)
        )

        return df
