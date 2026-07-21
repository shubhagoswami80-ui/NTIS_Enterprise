"""
NTIS Replay Timeline
"""
from datetime import datetime

class ReplayTimeline:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append({"time": datetime.now().isoformat(), "event": event})
