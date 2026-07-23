"""
HMME V1.6 Master Controller

Purpose:
Single execution controller for HMME V1.6 pipeline.
"""

from similarity_core.integration.hmme_historical_data_loader_v16 import (
    HMMEHistoricalDataLoaderV16
)
from similarity_core.integration.hmme_replay_dataset_builder_v16 import (
    HMMEReplayDatasetBuilderV16
)
from similarity_core.integration.hmme_memory_manager_v16 import (
    HMMEMemoryManagerV16
)
from similarity_core.integration.hmme_learning_engine_v16 import (
    HMMELearningEngineV16
)
from similarity_core.integration.hmme_calibration_engine_v16 import (
    HMMECalibrationEngineV16
)
from similarity_core.integration.hmme_probability_adapter_v16 import (
    HMMEProbabilityAdapterV16
)


class HMMEV16MasterController:

    def run(self):

        result = {}

        loader = HMMEHistoricalDataLoaderV16()
        result["historical"] = {
            "predictions": len(loader.load_predictions()),
            "outcomes": len(loader.load_outcomes())
        }

        result["replay"] = HMMEReplayDatasetBuilderV16().build()

        result["memory"] = HMMEMemoryManagerV16().build_memory()

        result["learning"] = HMMELearningEngineV16().learn()

        result["calibration"] = HMMECalibrationEngineV16().calibrate()

        result["probability"] = (
            HMMEProbabilityAdapterV16()
            .get_probability_context()
        )

        return {
            "status": "HMME_V1_6_COMPLETED",
            "pipeline": result
        }
