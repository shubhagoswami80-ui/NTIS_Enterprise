class PatternFingerprintRecord:

    def __init__(
        self,
        pattern_classification=None,
        pattern_dna=None,
        business_pattern_id=None,
        fingerprint_version=None,
        normalized_features=None,
    ):
        self.pattern_classification = pattern_classification
        self.pattern_dna = pattern_dna
        self.business_pattern_id = business_pattern_id
        self.fingerprint_version = fingerprint_version
        self.normalized_features = normalized_features

    def to_dict(self):
        return {
            "pattern_classification": self.pattern_classification,
            "pattern_dna": self.pattern_dna,
            "business_pattern_id": self.business_pattern_id,
            "fingerprint_version": self.fingerprint_version,
            "normalized_features": self.normalized_features,
        }

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            return None

        return cls(
            pattern_classification=payload.get("pattern_classification"),
            pattern_dna=payload.get("pattern_dna"),
            business_pattern_id=payload.get("business_pattern_id"),
            fingerprint_version=payload.get("fingerprint_version"),
            normalized_features=payload.get("normalized_features"),
        )


class PatternFingerprintContract:

    @staticmethod
    def validate(record):
        if record is None:
            return {"valid": False, "reason": "record is None"}

        if isinstance(record, PatternFingerprintRecord):
            record_dict = record.to_dict()
        elif isinstance(record, dict):
            record_dict = record
        else:
            return {"valid": False, "reason": "unsupported record type"}

        if not isinstance(record_dict.get("pattern_classification"), str):
            return {"valid": False, "reason": "pattern_classification must be a string"}

        if not isinstance(record_dict.get("pattern_dna"), str):
            return {"valid": False, "reason": "pattern_dna must be a string"}

        if not isinstance(record_dict.get("business_pattern_id"), str):
            return {"valid": False, "reason": "business_pattern_id must be a string"}

        if not isinstance(record_dict.get("fingerprint_version"), str):
            return {"valid": False, "reason": "fingerprint_version must be a string"}

        if not isinstance(record_dict.get("normalized_features"), dict):
            return {"valid": False, "reason": "normalized_features must be a dictionary"}

        return {"valid": True, "reason": "valid"}
