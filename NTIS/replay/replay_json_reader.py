import json
from pathlib import Path
class ReplayJsonReader:
    @staticmethod
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
