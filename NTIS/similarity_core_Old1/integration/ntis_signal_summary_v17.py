
"""
NTIS Signal Summary V17
"""

class NTISSignalSummaryV17:

    def summarize(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Signal Summary"] = "READY"

        return out
