"""
NTIS Replay Batch Runner
"""
class ReplayBatchRunner:
    def run(self, items, func):
        return [func(item) for item in items]
