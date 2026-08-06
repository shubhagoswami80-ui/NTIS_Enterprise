class PatternRepositoryRecord:

    def __init__(
        self,
        symbol=None,
        business_pattern_id=None,
        pattern_classification=None,
        pattern_dna=None,
        fingerprint_version=None,
        first_seen=None,
        last_seen=None,
        occurrences=None,
        wins=None,
        losses=None,
        pending=None,
        success_rate=None,
        average_return=None,
        confidence=None,
        lifecycle_status=None,
        normalized_features=None,
        evidence_vector=None,
    ):
        self.symbol = symbol
        self.business_pattern_id = business_pattern_id
        self.pattern_classification = pattern_classification
        self.pattern_dna = pattern_dna
        self.fingerprint_version = fingerprint_version
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.occurrences = occurrences
        self.wins = wins
        self.losses = losses
        self.pending = pending
        self.success_rate = success_rate
        self.average_return = average_return
        self.confidence = confidence
        self.lifecycle_status = lifecycle_status
        self.normalized_features = normalized_features
        self.evidence_vector = evidence_vector

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "business_pattern_id": self.business_pattern_id,
            "pattern_classification": self.pattern_classification,
            "pattern_dna": self.pattern_dna,
            "fingerprint_version": self.fingerprint_version,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "occurrences": self.occurrences,
            "wins": self.wins,
            "losses": self.losses,
            "pending": self.pending,
            "success_rate": self.success_rate,
            "average_return": self.average_return,
            "confidence": self.confidence,
            "lifecycle_status": self.lifecycle_status,
            "normalized_features": self.normalized_features,
            "evidence_vector": self.evidence_vector,
        }

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            return None

        return cls(
            symbol=payload.get("symbol"),
            business_pattern_id=payload.get("business_pattern_id"),
            pattern_classification=payload.get("pattern_classification"),
            pattern_dna=payload.get("pattern_dna"),
            fingerprint_version=payload.get("fingerprint_version"),
            first_seen=payload.get("first_seen"),
            last_seen=payload.get("last_seen"),
            occurrences=payload.get("occurrences"),
            wins=payload.get("wins"),
            losses=payload.get("losses"),
            pending=payload.get("pending"),
            success_rate=payload.get("success_rate"),
            average_return=payload.get("average_return"),
            confidence=payload.get("confidence"),
            lifecycle_status=payload.get("lifecycle_status"),
            normalized_features=payload.get("normalized_features"),
            evidence_vector=payload.get("evidence_vector"),
        )


class PatternRepositoryContract:

    @staticmethod
    def validate(record):
        if record is None:
            return {"valid": False, "reason": "record is None"}

        if isinstance(record, PatternRepositoryRecord):
            record_dict = record.to_dict()
        elif isinstance(record, dict):
            record_dict = record
        else:
            return {"valid": False, "reason": "unsupported record type"}

        if not isinstance(record_dict.get("symbol"), str):
            return {"valid": False, "reason": "symbol must be a string"}

        if not isinstance(record_dict.get("business_pattern_id"), str):
            return {"valid": False, "reason": "business_pattern_id must be a string"}

        if not isinstance(record_dict.get("pattern_classification"), str):
            return {"valid": False, "reason": "pattern_classification must be a string"}

        if not isinstance(record_dict.get("pattern_dna"), str):
            return {"valid": False, "reason": "pattern_dna must be a string"}

        if not isinstance(record_dict.get("fingerprint_version"), str):
            return {"valid": False, "reason": "fingerprint_version must be a string"}

        if not isinstance(record_dict.get("first_seen"), str):
            return {"valid": False, "reason": "first_seen must be a string"}

        if not isinstance(record_dict.get("last_seen"), str):
            return {"valid": False, "reason": "last_seen must be a string"}

        if not isinstance(record_dict.get("occurrences"), int):
            return {"valid": False, "reason": "occurrences must be an integer"}

        if not isinstance(record_dict.get("wins"), int):
            return {"valid": False, "reason": "wins must be an integer"}

        if not isinstance(record_dict.get("losses"), int):
            return {"valid": False, "reason": "losses must be an integer"}

        if not isinstance(record_dict.get("pending"), int):
            return {"valid": False, "reason": "pending must be an integer"}

        if not isinstance(record_dict.get("success_rate"), (int, float)):
            return {"valid": False, "reason": "success_rate must be numeric"}

        if not isinstance(record_dict.get("average_return"), (int, float)):
            return {"valid": False, "reason": "average_return must be numeric"}

        if not isinstance(record_dict.get("confidence"), (int, float)):
            return {"valid": False, "reason": "confidence must be numeric"}

        if not isinstance(record_dict.get("lifecycle_status"), str):
            return {"valid": False, "reason": "lifecycle_status must be a string"}

        if record_dict.get("normalized_features") is not None and not isinstance(record_dict.get("normalized_features"), dict):
            return {"valid": False, "reason": "normalized_features must be a dictionary"}

        if record_dict.get("evidence_vector") is not None and not isinstance(record_dict.get("evidence_vector"), dict):
            return {"valid": False, "reason": "evidence_vector must be a dictionary"}

        return {"valid": True, "reason": "valid"}
