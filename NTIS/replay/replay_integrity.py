"""
NTIS Replay Integrity Checks
"""
class ReplayIntegrity:
    @staticmethod
    def check(df):
        return {
            "rows": len(df),
            "duplicates": int(df.duplicated().sum()),
            "missing_values": int(df.isna().sum().sum())
        }
