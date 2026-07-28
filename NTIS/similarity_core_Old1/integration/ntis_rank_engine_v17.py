
"""
NTIS Rank Engine V17
"""

class NTISRankEngineV17:

    def rank(self, df):

        if df.empty:
            return df

        out = df.copy()

        if "Probability %" in out.columns:
            out = out.sort_values(
                "Probability %",
                ascending=False
            )

        out["Rank"] = range(1, len(out)+1)

        return out
