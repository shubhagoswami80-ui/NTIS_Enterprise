"""
HMME Production Runtime Adapter V1.6

Purpose:
Additive adapter for connecting HMME V1.6
with existing NTIS production runtime.

Does not modify production_runtime.py.
"""

from similarity_core.integration.hmme_runtime_patch_v16 import (
    HMMERuntimePatchV16
)


class HMMEProductionRuntimeAdapterV16:

    def __init__(self):
        self.patch = HMMERuntimePatchV16()

    def execute(self):

        return {
            "status": "HMME_RUNTIME_ADAPTER_EXECUTED",
            "result": self.patch.execute()
        }
