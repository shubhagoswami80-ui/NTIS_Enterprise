"""
NTIS Replay Result Writer
"""
from pathlib import Path
import json

class ReplayResultWriter:
    @staticmethod
    def write(result, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
