from pathlib import Path

class ReplayYAMLWriter:
    @staticmethod
    def write(data, path):
        lines = [f"{k}: {v}" for k, v in data.items()]
        Path(path).write_text("\n".join(lines), encoding="utf-8")
