"""
EOD Intelligence Context Engine V17

Step 2:
Converts EOD intelligence fields into a unified swing context.
"""

import pandas as pd


class EODIntelligenceContextEngineV17:

    def build_context(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Swing Bias"] = "NEUTRAL"
        out["Confidence"] = "LOW"

        if "Price Intelligence" in out.columns and "OI Intelligence" in out.columns:

            out.loc[
                (out["Price Intelligence"] == "POSITIVE") &
                (out["OI Intelligence"] == "LONG_BUILDUP"),
                "Swing Bias"
            ] = "BULLISH"

            out.loc[
                (out["Price Intelligence"] == "NEGATIVE") &
                (out["OI Intelligence"] == "SHORT_BUILDUP"),
                "Swing Bias"
            ] = "BEARISH"

        if "Swing Bias" in out.columns:
            out.loc[
                out["Swing Bias"] != "NEUTRAL",
                "Confidence"
            ] = "MEDIUM"

        return out
