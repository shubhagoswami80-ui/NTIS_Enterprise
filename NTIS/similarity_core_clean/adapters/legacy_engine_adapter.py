class LegacyEngineAdapter:

    def __init__(self):
        self.name = "hmme_engine_adapter"


    def connect(self):

        try:
            from similarity.hmme_engine import HMMEEngine

            return {
                "status": "CONNECTED",
                "engine": HMMEEngine
            }

        except Exception as e:

            return {
                "status": "FAILED",
                "error": str(e)
            }