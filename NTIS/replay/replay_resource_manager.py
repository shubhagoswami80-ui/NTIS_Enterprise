"""
NTIS Replay Resource Manager
"""
class ReplayResourceManager:
    def __init__(self):
        self._resources = {}

    def add(self, name, resource):
        self._resources[name] = resource

    def get(self, name):
        return self._resources.get(name)
