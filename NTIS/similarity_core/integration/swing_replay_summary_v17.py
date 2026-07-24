
"""
Swing Replay Summary V17
"""

class SwingReplaySummaryV17:

    def summarize(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Replay Summary"] = "PENDING"

        return out
