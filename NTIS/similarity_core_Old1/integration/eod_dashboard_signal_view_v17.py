
"""
EOD Dashboard Signal View V17
"""

class EODDashboardSignalViewV17:

    def prepare(self, df):

        if df.empty:
            return df

        columns = [
            "Symbol",
            "Trade Decision",
            "Swing Setup",
            "Probability %",
            "Confidence Level"
        ]

        available = [c for c in columns if c in df.columns]

        return df[available].copy()
