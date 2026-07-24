"""
Swing Intelligence Scorer V17

Converts intelligence context into a swing score.
"""

import pandas as pd


class SwingIntelligenceScorerV17:

    def score(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Swing Score"] = 0

        if "Swing Bias" in out.columns:
            out.loc[
                out["Swing Bias"] == "BULLISH",
                "Swing Score"
            ] += 40

            out.loc[
                out["Swing Bias"] == "BEARISH",
                "Swing Score"
            ] -= 40

        if "Volume Intelligence" in out.columns:
            out.loc[
                out["Volume Intelligence"] == "CONFIRMED",
                "Swing Score"
            ] += 20

        if "IV Intelligence" in out.columns:
            out.loc[
                out["IV Intelligence"] == "FALLING",
                "Swing Score"
            ] += 10

        out["Swing Signal"] = "NEUTRAL"

        out.loc[
            out["Swing Score"] >= 50,
            "Swing Signal"
        ] = "BUY"

        out.loc[
            out["Swing Score"] <= -50,
            "Swing Signal"
        ] = "SELL"

        return out
