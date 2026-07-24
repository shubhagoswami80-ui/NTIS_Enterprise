
"""
EOD Dashboard Data Provider V17
"""

class EODDashboardDataProviderV17:

    def prepare(self, df):

        if df.empty:
            return df

        return df.copy()
