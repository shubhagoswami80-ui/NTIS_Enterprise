
"""
EOD Dashboard Pipeline V17
"""

class EODDashboardPipelineV17:

    def run(self, df, provider, summary):

        df = provider.prepare(df)
        df = summary.build(df)

        return df
