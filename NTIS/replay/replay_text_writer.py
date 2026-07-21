from pathlib import Path

class ReplayTextWriter:
    @staticmethod
    def write(text, path):
        Path(path).write_text(str(text), encoding="utf-8")
