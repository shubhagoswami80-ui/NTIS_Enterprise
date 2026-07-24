
"""
NTIS Probability Reporting Pipeline V17
"""

class NTISProbabilityReportingPipelineV17:

    def run(self, df, metrics_engine, summary_engine):

        df = metrics_engine.calculate(df)
        df = summary_engine.generate(df)

        return df
