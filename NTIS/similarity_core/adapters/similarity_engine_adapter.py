class SimilarityEngineAdapter:

    def connect(self):

        try:
            from similarity.historical_similarity_engine import (
                HistoricalSimilarityEngine
            )

            return {
                "status": "CONNECTED",
                "engine": HistoricalSimilarityEngine
            }

        except Exception as e:

            return {
                "status": "FAILED",
                "error": str(e)
            }