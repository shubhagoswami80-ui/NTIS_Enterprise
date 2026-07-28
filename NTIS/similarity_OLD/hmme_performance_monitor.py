"""
HMME-15 Performance Monitor
"""
import time

class HMMEPerformanceMonitor:

    def start(self):
        return time.time()

    def elapsed(self, start):
        return time.time() - start
