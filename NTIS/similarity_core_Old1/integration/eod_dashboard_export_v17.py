
"""
EOD Dashboard Export V17
"""

class EODDashboardExportV17:

    def prepare(self, df):

        if df.empty:
            return df

        return df.copy()
