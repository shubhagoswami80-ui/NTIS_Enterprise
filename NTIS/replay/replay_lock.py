"""
NTIS Replay Lock
"""
from threading import Lock

class ReplayLock:
    def __init__(self):
        self._lock = Lock()

    def __enter__(self):
        self._lock.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()
