"""
NTIS Replay History
"""
class ReplayHistory:
    def __init__(self):
        self._history = []

    def add(self, record):
        self._history.append(record)

    def all(self):
        return list(self._history)
