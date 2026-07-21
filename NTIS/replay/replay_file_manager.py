"""
NTIS Replay File Manager
"""
from pathlib import Path
class ReplayFileManager:
    @staticmethod
    def ensure(path):
        Path(path).mkdir(parents=True, exist_ok=True)
        return Path(path)
