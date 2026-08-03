from similarity_core.adapters.legacy_engine_adapter import (
    LegacyEngineAdapter
)

from similarity_core.adapters.similarity_engine_adapter import (
    SimilarityEngineAdapter
)

from similarity_core.adapters.probability_engine_adapter import (
    ProbabilityEngineAdapter
)

from similarity_core.adapters.calibration_adapter import (
    CalibrationAdapter
)



class FunctionalGateway:


    def connect_all(self):

        return {

            "legacy":
            LegacyEngineAdapter()
            .connect(),

            "similarity":
            SimilarityEngineAdapter()
            .connect(),

            "probability":
            ProbabilityEngineAdapter()
            .connect(),

            "calibration":
            CalibrationAdapter()
            .connect()

        }