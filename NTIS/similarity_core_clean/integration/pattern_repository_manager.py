from datetime import datetime

from similarity_core_clean.integration.pattern_repository_contract import (
    PatternRepositoryContract,
    PatternRepositoryRecord,
)


class PatternRepositoryManager:

    def __init__(self):
        self.status = "READY"

    @staticmethod
    def _payload_to_dict(record):
        if isinstance(record, PatternRepositoryRecord):
            return record.to_dict()
        if isinstance(record, dict):
            return record
        return {}

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
    def _merge_last_seen(existing_last_seen, incoming_last_seen):
        if not isinstance(existing_last_seen, str):
            return incoming_last_seen
        if not isinstance(incoming_last_seen, str):
            return existing_last_seen
        try:
            existing_dt = datetime.fromisoformat(existing_last_seen.replace("Z", "+00:00"))
            incoming_dt = datetime.fromisoformat(incoming_last_seen.replace("Z", "+00:00"))
            return incoming_last_seen if incoming_dt >= existing_dt else existing_last_seen
        except Exception:
            return incoming_last_seen if incoming_last_seen >= existing_last_seen else existing_last_seen

    def _find_existing(self, business_pattern_id, repository_records):
        if business_pattern_id is None:
            return None

        if repository_records is None:
            return None

        if isinstance(repository_records, dict):
            candidate = repository_records.get(business_pattern_id)
            if candidate is not None:
                return candidate
            records = repository_records.values()
        elif isinstance(repository_records, list):
            records = repository_records
        else:
            return None

        for record in records:
            record_dict = self._payload_to_dict(record)
            if record_dict.get("business_pattern_id") == business_pattern_id:
                return record
        return None

    def _build_summary(self, record_dict, action):
        return {
            "business_pattern_id": record_dict.get("business_pattern_id"),
            "symbol": record_dict.get("symbol"),
            "pattern_classification": record_dict.get("pattern_classification"),
            "pattern_dna": record_dict.get("pattern_dna"),
            "occurrences": record_dict.get("occurrences"),
            "wins": record_dict.get("wins"),
            "losses": record_dict.get("losses"),
            "pending": record_dict.get("pending"),
            "success_rate": record_dict.get("success_rate"),
            "average_return": record_dict.get("average_return"),
            "confidence": record_dict.get("confidence"),
            "last_seen": record_dict.get("last_seen"),
            "lifecycle_status": record_dict.get("lifecycle_status"),
            "repository_action": action,
        }

    def manage_repository_record(self, incoming_record, repository_records=None):
        self.status = "PROCESSING"

        incoming_dict = self._payload_to_dict(incoming_record)
        fingerprint_validation = PatternRepositoryContract.validate(incoming_dict)
        if not fingerprint_validation.get("valid"):
            self.status = "REJECTED"
            return {
                "status": "REJECTED_INPUT",
                "repository_action": "INVALID_INCOMING_RECORD",
                "repository_record": None,
                "repository_summary": {
                    "valid": False,
                    "reason": fingerprint_validation.get("reason"),
                },
            }

        business_pattern_id = incoming_dict.get("business_pattern_id")
        existing_record = self._find_existing(business_pattern_id, repository_records)
        if existing_record is None:
            self.status = "PASSTHROUGH"
            record_dict = incoming_dict.copy()
            if isinstance(record_dict.get("normalized_features"), dict):
                record_dict["normalized_features"] = record_dict["normalized_features"].copy()
            if isinstance(record_dict.get("evidence_vector"), dict):
                record_dict["evidence_vector"] = record_dict["evidence_vector"].copy()
            self._ensure_numeric_defaults(record_dict)
            return {
                "status": "REPOSITORY_NOT_FOUND",
                "repository_action": "PASSTHROUGH",
                "repository_record": record_dict,
                "repository_summary": self._build_summary(record_dict, "PASSTHROUGH"),
            }

        existing_dict = self._payload_to_dict(existing_record)
        existing_validation = PatternRepositoryContract.validate(existing_dict)
        if not existing_validation.get("valid"):
            self.status = "REJECTED"
            return {
                "status": "REJECTED_EXISTING",
                "repository_action": "INVALID_EXISTING_RECORD",
                "repository_record": None,
                "repository_summary": {
                    "valid": False,
                    "reason": existing_validation.get("reason"),
                },
            }

        updated_record = existing_dict.copy()
        updated_record["occurrences"] = self._coerce_int(existing_dict.get("occurrences", 0)) + self._coerce_int(incoming_dict.get("occurrences", 1))
        updated_record["wins"] = self._coerce_int(existing_dict.get("wins", 0)) + self._coerce_int(incoming_dict.get("wins", 0))
        updated_record["losses"] = self._coerce_int(existing_dict.get("losses", 0)) + self._coerce_int(incoming_dict.get("losses", 0))
        updated_record["pending"] = self._coerce_int(existing_dict.get("pending", 0)) + self._coerce_int(incoming_dict.get("pending", 0))

        occurrences = updated_record["occurrences"] or 0
        wins = updated_record["wins"] or 0
        losses = updated_record["losses"] or 0

        updated_record["success_rate"] = float(wins) / occurrences if occurrences > 0 else 0.0

        existing_avg = self._coerce_float(existing_dict.get("average_return")) or 0.0
        incoming_avg = self._coerce_float(incoming_dict.get("average_return")) or 0.0
        existing_count = self._coerce_int(existing_dict.get("occurrences", 0)) or 0
        incoming_count = self._coerce_int(incoming_dict.get("occurrences", 1)) or 0
        total_count = existing_count + incoming_count
        if total_count > 0:
            updated_record["average_return"] = (
                ((existing_avg * existing_count) + (incoming_avg * incoming_count)) / total_count
            )
        else:
            updated_record["average_return"] = 0.0

        existing_confidence = self._coerce_float(existing_dict.get("confidence")) or 0.0
        incoming_confidence = self._coerce_float(incoming_dict.get("confidence")) or 0.0
        updated_record["confidence"] = (
            (existing_confidence * existing_count + incoming_confidence * incoming_count) / total_count
            if total_count > 0
            else 0.0
        )

        updated_record["last_seen"] = self._merge_last_seen(existing_dict.get("last_seen"), incoming_dict.get("last_seen"))
        updated_record["lifecycle_status"] = incoming_dict.get("lifecycle_status") or existing_dict.get("lifecycle_status")

        # Preserve PDNA memory fields on update
        if incoming_dict.get("normalized_features") is not None:
            updated_record["normalized_features"] = incoming_dict.get("normalized_features")
        else:
            updated_record["normalized_features"] = existing_dict.get("normalized_features")

        if incoming_dict.get("evidence_vector") is not None:
            updated_record["evidence_vector"] = incoming_dict.get("evidence_vector")
        else:
            updated_record["evidence_vector"] = existing_dict.get("evidence_vector")

        if incoming_dict.get("historical_outcome") is not None:
            updated_record["historical_outcome"] = incoming_dict.get("historical_outcome")
        else:
            updated_record["historical_outcome"] = existing_dict.get("historical_outcome")

        repository_validation = PatternRepositoryContract.validate(updated_record)
        if not repository_validation.get("valid"):
            self.status = "REJECTED"
            return {
                "status": "REJECTED_UPDATED_RECORD",
                "repository_action": "INVALID_UPDATED_RECORD",
                "repository_record": updated_record,
                "repository_summary": {
                    "valid": False,
                    "reason": repository_validation.get("reason"),
                },
            }

        self.status = "UPDATED"
        return {
            "status": "REPOSITORY_UPDATED",
            "repository_action": "UPDATE_EXISTING",
            "repository_record": updated_record,
            "repository_summary": self._build_summary(updated_record, "UPDATE_EXISTING"),
        }

    def _ensure_numeric_defaults(self, record_dict):
        if record_dict.get("occurrences") is None:
            record_dict["occurrences"] = 1
        if record_dict.get("wins") is None:
            record_dict["wins"] = 0
        if record_dict.get("losses") is None:
            record_dict["losses"] = 0
        if record_dict.get("pending") is None:
            record_dict["pending"] = 0
        if record_dict.get("success_rate") is None:
            record_dict["success_rate"] = 0.0
        if record_dict.get("average_return") is None:
            record_dict["average_return"] = 0.0
        if record_dict.get("confidence") is None:
            record_dict["confidence"] = 0.0
