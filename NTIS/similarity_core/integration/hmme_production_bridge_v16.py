"""
HMME Production Bridge V1.6

Purpose:
Bridge HMME V1.6 intelligence status with NTIS runtime.
"""

from similarity_core.integration.hmme_v16_master_controller import (
    HMMEV16MasterController
)


class HMMEProductionBridgeV16:

    def __init__(self):
        self.controller = HMMEV16MasterController()

    def execute_hmme_layer(self):

        result = self.controller.run()

        return {
            "status": "HMME_LAYER_EXECUTED",
            "hmme": result
        }
