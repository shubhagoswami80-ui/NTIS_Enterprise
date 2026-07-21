"""
NTIS Replay Queue
"""
from collections import deque

class ReplayQueue:
    def __init__(self):
        self._queue = deque()

    def push(self, item):
        self._queue.append(item)

    def pop(self):
        return self._queue.popleft() if self._queue else None
