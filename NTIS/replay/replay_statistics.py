"""
NTIS Replay Statistics
"""
class ReplayStatistics:
    @staticmethod
    def calculate(results):
        total = len(results)
        wins = sum(1 for r in results if r)
        losses = total - wins
        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins/total)*100,2) if total else 0
        }
