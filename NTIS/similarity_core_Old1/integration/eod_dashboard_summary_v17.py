
"""
EOD Dashboard Summary V17
"""

class EODDashboardSummaryV17:

    def build(self, df):

        if df.empty:
            return df

        return df.head(20).copy()
