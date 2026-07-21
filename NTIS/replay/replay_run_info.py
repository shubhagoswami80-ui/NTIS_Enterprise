"""
NTIS Replay Run Information
"""
from datetime import datetime
class ReplayRunInfo:
    @staticmethod
    def create(name):
        return {"run_name": name, "started_at": datetime.now().isoformat()}
