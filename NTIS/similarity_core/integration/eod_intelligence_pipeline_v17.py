"""
EOD Intelligence Pipeline V17

Connects completed Step 2 intelligence modules.
"""

class EODIntelligencePipelineV17:

    def __init__(
        self,
        context_engine,
        scorer,
        confidence_engine,
        setup_engine
    ):
        self.context_engine = context_engine
        self.scorer = scorer
        self.confidence_engine = confidence_engine
        self.setup_engine = setup_engine

    def run(self, df):

        df = self.context_engine.build_context(df)
        df = self.scorer.score(df)
        df = self.confidence_engine.evaluate(df)
        df = self.setup_engine.build(df)

        return df
