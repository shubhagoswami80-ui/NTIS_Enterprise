"""
HMME-17 Batch Optimizer
"""
class HMMEBatchOptimizer:

    def __init__(self, batch_size=50000):
        self.batch_size = batch_size

    def get_batches(self, data):
        for i in range(0, len(data), self.batch_size):
            yield data[i:i+self.batch_size]
