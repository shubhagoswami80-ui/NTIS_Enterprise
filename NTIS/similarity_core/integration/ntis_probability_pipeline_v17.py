
"""
NTIS Probability Pipeline V17
"""

class NTISProbabilityPipelineV17:

    def run(self, df, probability_engine, rank_engine, summary_engine):

        df = probability_engine.calculate(df)
        df = rank_engine.rank(df)
        df = summary_engine.summarize(df)

        return df
