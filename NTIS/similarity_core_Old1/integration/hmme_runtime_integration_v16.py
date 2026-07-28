"""
HMME Runtime Integration V1.6

Purpose:
Connect HMME V1.6 intelligence outputs
with NTIS runtime execution.
"""

from pathlib import Path

from similarity_core.integration.hmme_probability_adapter_v16 import (
    HMMEProbabilityAdapterV16
)


class HMMERuntimeIntegrationV16:

    def __init__(self):
        self.adapter = HMMEProbabilityAdapterV16()

    def status(self):

        context = self.adapter.get_probability_context()

        return {
            "status": "CONNECTED",
            "hmme_probability": context
        }
