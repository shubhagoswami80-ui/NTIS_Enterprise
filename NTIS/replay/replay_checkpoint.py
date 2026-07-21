"""
NTIS Replay Checkpoint
"""
from pathlib import Path
import json

class ReplayCheckpoint:
    @staticmethod
    def save(state, path):
        Path(path).write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")

    @staticmethod
    def load(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
