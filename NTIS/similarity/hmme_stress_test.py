"""
HMME-17 Stress Test
"""
import time

class HMMEStressTest:

    def run(self, function, *args, **kwargs):
        start = time.time()
        result = function(*args, **kwargs)
        return {
            "result": result,
            "execution_seconds": round(time.time()-start, 4)
        }
