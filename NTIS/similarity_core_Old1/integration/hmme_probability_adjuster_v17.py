
"""
HMME Probability Adjuster V17
"""

class HMMEProbabilityAdjusterV17:

    def adjust(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Probability Status"] = "ADJUSTED"

        return out
