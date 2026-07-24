"""
EOD Intelligence Engine V17

Core intelligence layer.
Reads NTIS processed data and creates intelligence attributes.
"""

import pandas as pd


class EODIntelligenceEngineV17:

    def analyze(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Price Intelligence"] = "NEUTRAL"
        out["OI Intelligence"] = "NEUTRAL"

        if "Price Chg %" in out.columns:
            out.loc[out["Price Chg %"] > 0, "Price Intelligence"] = "POSITIVE"
            out.loc[out["Price Chg %"] < 0, "Price Intelligence"] = "NEGATIVE"

        if all(c in out.columns for c in ["Price Chg %", "OI Chg %"]):

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

        out["Market Intelligence"] = (
            out["Price Intelligence"]
            + "_"
            + out["OI Intelligence"]
        )

        return out
