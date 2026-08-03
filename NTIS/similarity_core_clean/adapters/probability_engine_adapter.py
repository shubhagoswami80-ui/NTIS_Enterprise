class ProbabilityEngineAdapter:
    """
    Adapter contract between Similarity Core and NTIS Probability Engine.
    """

    def connect(self):

        try:
            from probability_engine import ProbabilityEngine

            return {
                "status": "CONNECTED",
                "engine": ProbabilityEngine,
                "interface": "ProbabilityEngine"
            }

        except Exception as e:

            return {
                "status": "FAILED",
                "error": str(e),
                "interface": "ProbabilityEngine"
            }

    def validate(self):

        result = self.connect()

        return {
            "valid": result.get("status") == "CONNECTED",
            "details": result
        }
