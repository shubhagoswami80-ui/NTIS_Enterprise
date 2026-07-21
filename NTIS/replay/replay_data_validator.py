"""
NTIS Replay Data Validator
"""
class ReplayDataValidator:
    @staticmethod
    def validate(df, required_columns):
        missing=[c for c in required_columns if c not in df.columns]
        return {"valid": len(missing)==0, "missing_columns": missing}
