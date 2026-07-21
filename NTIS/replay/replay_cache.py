"""
=========================================================
NTIS Replay Cache
Version : 1.0
Purpose :
    Cache replay data and calculations
    to improve performance.
=========================================================
"""

from pathlib import Path
import pickle


class ReplayCache:

    def __init__(self):
        self._cache = {}

    def get(self, key):

        return self._cache.get(key)

    def set(self, key, value):

        self._cache[key] = value

    def exists(self, key):

        return key in self._cache

    def clear(self):

        self._cache.clear()

    def save(self, file_path):

        file_path = Path(file_path)
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(file_path, "wb") as f:
            pickle.dump(self._cache, f)

    def load(self, file_path):

        file_path = Path(file_path)

        if not file_path.exists():
            return

        with open(file_path, "rb") as f:
            self._cache = pickle.load(f)