"""
NTIS Replay Session Manager
"""
from uuid import uuid4
from datetime import datetime

class ReplaySessionManager:
    def start(self):
        return {
            "session_id": str(uuid4()),
            "started_at": datetime.now().isoformat()
        }
