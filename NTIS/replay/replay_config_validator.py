"""
NTIS Replay Configuration Validator
"""
class ReplayConfigValidator:
    REQUIRED_KEYS = ("start_date","end_date","strategy")

    @classmethod
    def validate(cls, config: dict):
        missing = [k for k in cls.REQUIRED_KEYS if k not in config]
        if missing:
            raise ValueError(f"Missing configuration keys: {', '.join(missing)}")
        return True
