"""
NTIS Replay Index Builder
"""
class ReplayIndexBuilder:
    @staticmethod
    def build(records, key="Symbol"):
        return {r[key]: r for r in records if key in r}
