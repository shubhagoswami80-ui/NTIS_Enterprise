from similarity_core_clean.adapters.legacy_engine_adapter import LegacyEngineAdapter
from similarity_core_clean.adapters.similarity_engine_adapter import SimilarityEngineAdapter
from similarity_core_clean.adapters.probability_engine_adapter import ProbabilityEngineAdapter
from similarity_core_clean.adapters.calibration_adapter import CalibrationAdapter


class FunctionalGateway:
    """
    Central integration gateway for NTIS similarity stack.
    """

    def connect_all(self):

        adapters = {
            "legacy": LegacyEngineAdapter(),
            "similarity": SimilarityEngineAdapter(),
            "probability": ProbabilityEngineAdapter(),
            "calibration": CalibrationAdapter(),
        }

        connections = {}

        for name, adapter in adapters.items():
            try:
                connections[name] = adapter.connect()
            except Exception as exc:
                connections[name] = {
                    "status": "FAILED",
                    "error": str(exc)
                }

        return connections

    def health_check(self):

        connections = self.connect_all()

        return {
            "status": (
                "READY"
                if all(
                    item.get("status") == "CONNECTED"
                    for item in connections.values()
                )
                else "DEGRADED"
            ),
            "components": connections
        }
