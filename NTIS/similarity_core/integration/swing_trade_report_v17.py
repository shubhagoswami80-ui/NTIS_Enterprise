"""
Swing Trade Report Builder V17

Creates final swing trade report structure.
"""

class SwingTradeReportV17:

    def build(self, df):

        if df.empty:
            return df

        columns = [
            "Symbol",
            "Trade Decision",
            "Swing Setup",
            "Swing Score",
            "Confidence Level",
            "Validation Status",
            "Risk Reward"
        ]

        available = [
            c for c in columns
            if c in df.columns
        ]

        return df[available].copy()
