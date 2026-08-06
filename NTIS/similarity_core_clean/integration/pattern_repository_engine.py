from datetime import datetime

from similarity_core_clean.integration.pattern_fingerprint_contract import (
    PatternFingerprintContract,
    PatternFingerprintRecord,
)
from similarity_core_clean.integration.pattern_repository_contract import (
    PatternRepositoryContract,
    PatternRepositoryRecord,
)


class PatternRepositoryEngine:

    def __init__(self):
        self.status = "READY"

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _coerce_int(value):
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _build_timestamp(date_value=None):
        if isinstance(date_value, str) and date_value:
            return date_value
        if date_value is None:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return str(date_value)

    def _payload_to_dict(self, record):
        if isinstance(record, PatternFingerprintRecord):
            return record.to_dict()
        if isinstance(record, dict):
            return record
        return {}

    def _build_repository_record(self, fingerprint_payload):
        normalized_features = fingerprint_payload.get("normalized_features", {})

        symbol = normalized_features.get("symbol")
        if symbol is None:
            return None, "missing symbol in normalized_features"

        pattern_classification = fingerprint_payload.get("pattern_classification")
        pattern_dna = fingerprint_payload.get("pattern_dna")
        business_pattern_id = fingerprint_payload.get("business_pattern_id")
        fingerprint_version = fingerprint_payload.get("fingerprint_version")

        first_seen = self._build_timestamp(normalized_features.get("date"))
        last_seen = self._build_timestamp(normalized_features.get("date"))

        confidence = self._coerce_float(normalized_features.get("confidence"))
        if confidence is None:
            confidence = 0.0

        evidence_vector = fingerprint_payload.get("evidence_vector")
        if isinstance(evidence_vector, dict):
            evidence_vector = evidence_vector.copy()

        historical_outcome = fingerprint_payload.get("historical_outcome")

        repository_record = PatternRepositoryRecord(
            symbol=str(symbol),
            business_pattern_id=str(business_pattern_id),
            pattern_classification=str(pattern_classification),
            pattern_dna=str(pattern_dna),
            fingerprint_version=str(fingerprint_version),
            first_seen=str(first_seen),
            last_seen=str(last_seen),
            occurrences=1,
            wins=0,
            losses=0,
            pending=1,
            success_rate=0.0,
            average_return=0.0,
            confidence=confidence,
            lifecycle_status="NEW",
            normalized_features=normalized_features.copy(),
            evidence_vector=evidence_vector,
            historical_outcome=historical_outcome,
        )

        return repository_record, None

    def _build_repository_summary(self, repository_dict):
        return {
            "symbol": repository_dict.get("symbol"),
            "business_pattern_id": repository_dict.get("business_pattern_id"),
            "pattern_classification": repository_dict.get("pattern_classification"),
            "pattern_dna": repository_dict.get("pattern_dna"),
            "occurrences": repository_dict.get("occurrences"),
            "wins": repository_dict.get("wins"),
            "losses": repository_dict.get("losses"),
            "pending": repository_dict.get("pending"),
            "success_rate": repository_dict.get("success_rate"),
            "average_return": repository_dict.get("average_return"),
            "confidence": repository_dict.get("confidence"),
            "lifecycle_status": repository_dict.get("lifecycle_status"),
            "repository_ready": True,
        }

    def create_repository_record(self, fingerprint_record):
        self.status = "PROCESSING"

        payload = self._payload_to_dict(fingerprint_record)
        validation = PatternFingerprintContract.validate(payload)
        if not validation.get("valid"):
            self.status = "REJECTED"
            return {
                "status": "REJECTED_FINGERPRINT",
                "repository_status": "INVALID_FINGERPRINT",
                "repository_record": None,
                "repository_summary": {
                    "valid": False,
                    "reason": validation.get("reason"),
                },
            }

        repository_record, error = self._build_repository_record(payload)
        if repository_record is None:
            self.status = "REJECTED"
            return {
                "status": "REJECTED_REPOSITORY",
                "repository_status": "INVALID_REPOSITORY",
                "repository_record": None,
                "repository_summary": {
                    "valid": False,
                    "reason": error,
                },
            }

        repository_validation = PatternRepositoryContract.validate(repository_record)
        repository_dict = repository_record.to_dict()

        if not repository_validation.get("valid"):
            self.status = "REJECTED"
            return {
                "status": "REJECTED_REPOSITORY",
                "repository_status": "INVALID_REPOSITORY",
                "repository_record": repository_dict,
                "repository_summary": {
                    "valid": False,
                    "reason": repository_validation.get("reason"),
                },
            }

        self.status = "CREATED"

        repository_summary = self._build_repository_summary(repository_dict)

        return {
            "status": "REPOSITORY_CREATED",
            "repository_status": "REPOSITORY_READY",
            "repository_record": repository_dict,
            "repository_summary": repository_summary,
        }
