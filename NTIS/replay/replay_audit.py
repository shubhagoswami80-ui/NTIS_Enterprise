"""
NTIS Replay Audit
"""
from datetime import datetime

class ReplayAudit:
    def __init__(self):
        self.records=[]

    def add(self, action):
        self.records.append((datetime.now(), action))
