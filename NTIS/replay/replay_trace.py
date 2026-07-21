"""
NTIS Replay Trace
"""
class ReplayTrace:
    def __init__(self):
        self.entries = []

    def log(self, message):
        self.entries.append(message)
