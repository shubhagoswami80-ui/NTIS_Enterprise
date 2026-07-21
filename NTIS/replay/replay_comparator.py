"""
NTIS Replay Comparator
"""
class ReplayComparator:
    @staticmethod
    def compare(expected, actual):
        return {
            "match": expected == actual,
            "expected": expected,
            "actual": actual
        }
