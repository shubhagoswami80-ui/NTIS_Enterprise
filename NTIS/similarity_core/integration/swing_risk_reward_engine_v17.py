"""
Swing Risk Reward Engine V17
"""

class SwingRiskRewardEngineV17:

    def calculate(self, df):

        if df.empty:
            return df

        out = df.copy()

        out["Risk Reward"] = "UNKNOWN"

        if "Close" in out.columns:

            if "Support" in out.columns and "Resistance" in out.columns:

                out["Risk"] = out["Close"] - out["Support"]
                out["Reward"] = out["Resistance"] - out["Close"]

                out.loc[
                    out["Risk"] > 0,
                    "Risk Reward"
                ] = "CALCULATED"

        return out
