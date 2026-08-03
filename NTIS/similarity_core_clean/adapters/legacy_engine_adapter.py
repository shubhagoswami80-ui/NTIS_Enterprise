class LegacyEngineAdapter:

    def __init__(self):
        self.name = "hmme_runtime_adapter"

    def connect(self):

        try:
            from similarity_core_clean.integration.hmme_runtime_executor import HMMERuntimeExecutor

            return {
                "status": "CONNECTED",
                "engine": HMMERuntimeExecutor,
                "interface": "HMME Runtime Executor"
            }

        except Exception as e:

            return {
                "status": "FAILED",
                "error": str(e)
            }
