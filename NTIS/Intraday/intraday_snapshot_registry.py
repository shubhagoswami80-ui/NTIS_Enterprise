from pathlib import Path
import json

class SnapshotRegistry:
    def __init__(self, file="snapshot_registry.json"):
        self.file = Path(file)

    def register(self, snapshot):
        data = []
        if self.file.exists():
            data = json.loads(self.file.read_text())
        data.append(str(snapshot))
        self.file.write_text(json.dumps(data, indent=4))
        return True
