"""
Swing Setup Context Engine V17

Creates final swing setup context from intelligence outputs.
"""

import pandas as pd


class SwingSetupContextV17:

    def build(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Swing Setup"] = "NO_SETUP"

        if "Swing Signal" in out.columns and "Confidence Level" in out.columns:

            out.loc[
                (out["Swing Signal"] == "BUY") &
                (out["Confidence Level"].isin(["MEDIUM", "HIGH"])),
                "Swing Setup"
            ] = "BUY_SETUP"

            out.loc[
                (out["Swing Signal"] == "SELL") &
                (out["Confidence Level"].isin(["MEDIUM", "HIGH"])),
                "Swing Setup"
            ] = "SELL_SETUP"

        return out
