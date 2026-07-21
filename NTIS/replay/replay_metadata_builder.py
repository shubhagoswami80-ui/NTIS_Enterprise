"""
NTIS Replay Metadata Builder
"""
from datetime import datetime

class ReplayMetadataBuilder:
    @staticmethod
    def build(version="1.0"):
        return {
            "version": version,
            "generated_at": datetime.now().isoformat()
        }
