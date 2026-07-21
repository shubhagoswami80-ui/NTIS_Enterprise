"""
=========================================================
NTIS Replay Timer
Version : 1.0
Purpose :
    Measure execution time of Replay
    operations.
=========================================================
"""

import time


class ReplayTimer:

    def __init__(self):

        self._start = None
        self._end = None

    def start(self):

        self._start = time.perf_counter()
        self._end = None

    def stop(self):

        if self._start is None:
            return 0.0

        self._end = time.perf_counter()

        return self.elapsed()

    def elapsed(self):

        if self._start is None:
            return 0.0

        if self._end is None:
            return round(
                time.perf_counter() - self._start,
                4,
            )

        return round(
            self._end - self._start,
            4,
        )

    def reset(self):

        self._start = None
        self._end = None