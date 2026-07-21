from pathlib import Path

class ReplayYAMLReader:
    @staticmethod
    def read(path):
        result = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                result[k.strip()] = v.strip()
        return result
