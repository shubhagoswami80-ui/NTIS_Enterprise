"""
EOD Intelligence Engine V17 V2

Adds:
- Price Intelligence
- OI Intelligence
- Volume Intelligence
- IV Intelligence
- Support/Resistance Intelligence hooks
- Combined Swing Intelligence

Reads existing NTIS datasets.
Does not duplicate raw data.
"""

import pandas as pd


class EODIntelligenceEngineV17:

    def analyze(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Price Intelligence"] = "NEUTRAL"
        out["OI Intelligence"] = "NEUTRAL"
        out["Volume Intelligence"] = "UNKNOWN"
        out["IV Intelligence"] = "UNKNOWN"
        out["Risk Intelligence"] = "UNKNOWN"

        if "Price Chg %" in out.columns:
            out.loc[out["Price Chg %"] > 0, "Price Intelligence"] = "POSITIVE"
            out.loc[out["Price Chg %"] < 0, "Price Intelligence"] = "NEGATIVE"

        if "Price Chg %" in out.columns and "OI Chg %" in out.columns:

            out.loc[
                (out["Price Chg %"] > 0) &
                (out["OI Chg %"] > 0),
                "OI Intelligence"
            ] = "LONG_BUILDUP"

            out.loc[
                (out["Price Chg %"] < 0) &
                (out["OI Chg %"] > 0),
                "OI Intelligence"
            ] = "SHORT_BUILDUP"

            out.loc[
                (out["Price Chg %"] > 0) &
                (out["OI Chg %"] < 0),
                "OI Intelligence"
            ] = "SHORT_COVERING"

        if "Volume Chg %" in out.columns:
            out.loc[
                out["Volume Chg %"] > 0,
                "Volume Intelligence"
            ] = "CONFIRMED"

        if "IV Chg %" in out.columns:
            out.loc[
                out["IV Chg %"] > 0,
                "IV Intelligence"
            ] = "RISING"

            out.loc[
                out["IV Chg %"] < 0,
                "IV Intelligence"
            ] = "FALLING"

        out["Swing Intelligence"] = (
            out["Price Intelligence"]
            + "_"
            + out["OI Intelligence"]
            + "_"
            + out["Volume Intelligence"]
        )

        return out
