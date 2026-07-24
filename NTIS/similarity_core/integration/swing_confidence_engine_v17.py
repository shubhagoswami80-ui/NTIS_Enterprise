"""
Swing Confidence Engine V17

Converts swing score and context into confidence level.
"""

import pandas as pd


class SwingConfidenceEngineV17:

    def evaluate(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Confidence Level"] = "LOW"

        if "Swing Score" in out.columns:
            out.loc[
                out["Swing Score"].abs() >= 50,
                "Confidence Level"
            ] = "MEDIUM"

            out.loc[
                out["Swing Score"].abs() >= 70,
                "Confidence Level"
            ] = "HIGH"

        return out
