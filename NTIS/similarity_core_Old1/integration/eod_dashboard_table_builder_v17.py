
"""
EOD Dashboard Table Builder V17
"""

class EODDashboardTableBuilderV17:

    def build(self, df):

        if df is None:
            return df

        return df.copy()
