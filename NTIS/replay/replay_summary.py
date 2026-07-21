"""
NTIS Replay Summary
"""
class ReplaySummary:
    @staticmethod
    def build(total=0, success=0, failed=0):
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "accuracy": round((success/total)*100,2) if total else 0
        }
