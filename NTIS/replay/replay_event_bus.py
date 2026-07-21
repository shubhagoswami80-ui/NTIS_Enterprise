"""
NTIS Replay Event Bus
"""
class ReplayEventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event, handler):
        self._subscribers.setdefault(event, []).append(handler)

    def publish(self, event, payload=None):
        for handler in self._subscribers.get(event, []):
            handler(payload)
