
"""
NTIS Probability Engine V17
"""

class NTISProbabilityEngineV17:

    def calculate(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Probability %"] = 0

        if "Swing Score" in out.columns:
            out["Probability %"] = (
                50 + out["Swing Score"]
            ).clip(0, 100)

        return out
