class ProbabilityEngineAdapter:

    def connect(self):

        try:

            from probability_engine import ProbabilityEngine

            return {
                "status": "CONNECTED",
                "engine": ProbabilityEngine
            }

        except Exception as e:

            return {
                "status": "FAILED",
                "error": str(e)
            }