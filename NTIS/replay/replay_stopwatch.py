import time

class ReplayStopwatch:
    def start(self):
        self._t = time.perf_counter()
    def elapsed(self):
        return time.perf_counter() - self._t
