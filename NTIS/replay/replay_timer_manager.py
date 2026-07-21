import time
class ReplayTimerManager:
    def start(self): self.t=time.perf_counter()
    def stop(self): return time.perf_counter()-self.t
