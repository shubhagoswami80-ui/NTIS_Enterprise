import json
from pathlib import Path
class ReplayJsonWriter:
    @staticmethod
    def write(data,path):
        Path(path).write_text(json.dumps(data,indent=2,default=str),encoding="utf-8")
