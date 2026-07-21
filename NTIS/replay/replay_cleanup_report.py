"""
NTIS Replay Cleanup Report
"""
class ReplayCleanupReport:
    @staticmethod
    def build(files_removed):
        return {
            "files_removed": len(files_removed),
            "items": list(files_removed)
        }
