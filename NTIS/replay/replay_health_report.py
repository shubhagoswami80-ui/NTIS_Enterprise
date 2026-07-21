"""
NTIS Replay Health Report
"""
class ReplayHealthReport:
    @staticmethod
    def build(status="OK", issues=None):
        return {
            "status": status,
            "issues": issues or []
        }
