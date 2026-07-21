"""
NTIS Replay Snapshot
"""
import copy

class ReplaySnapshot:
    @staticmethod
    def create(state):
        return copy.deepcopy(state)
