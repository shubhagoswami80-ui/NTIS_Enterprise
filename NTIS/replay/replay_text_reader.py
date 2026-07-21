from pathlib import Path

class ReplayTextReader:
    @staticmethod
    def read(path):
        return Path(path).read_text(encoding="utf-8")
