"""
HMME-20 Similarity Optimizer
"""

class SimilarityOptimizer:

    def optimize_candidates(self, data, limit=500):
        if data is None:
            return []
        return data[:limit]
