"""
NTIS Replay Manifest Builder
"""
from datetime import datetime

class ReplayManifestBuilder:
    @staticmethod
    def build(files):
        return {
            "generated_at": datetime.now().isoformat(),
            "files": list(files),
            "count": len(list(files))
        }
