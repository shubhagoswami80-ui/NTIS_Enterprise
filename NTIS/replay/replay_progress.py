"""
NTIS Replay Progress
"""
class ReplayProgress:
    def __init__(self):
        self.current = 0
        self.total = 0

    def update(self, current, total):
        self.current = current
        self.total = total

    @property
    def percent(self):
        return round((self.current/self.total)*100,2) if self.total else 0
