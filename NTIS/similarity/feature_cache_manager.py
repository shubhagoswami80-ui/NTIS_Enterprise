"""
HMME-20 Feature Cache Manager
"""

class FeatureCacheManager:

    def __init__(self):
        self.cache = {}

    def store(self, key, value):
        self.cache[key] = value

    def get(self, key):
        return self.cache.get(key)
