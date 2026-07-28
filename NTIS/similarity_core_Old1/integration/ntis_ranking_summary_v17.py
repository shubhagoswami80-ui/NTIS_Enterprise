
"""
NTIS Ranking Summary V17
"""

class NTISRankingSummaryV17:

    def generate(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Ranking Status"] = "COMPLETED"

        return out
