from math import sqrt

from similarity_core_clean.integration.pattern_repository_contract import (
    PatternRepositoryContract,
    PatternRepositoryRecord,
)


class HistoricalPatternIntelligence:

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
    def _coerce_int(value):
        try:
            return int(value)
        except Exception:
            return 0

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _gather_records(repository_records):
        if repository_records is None:
            return []

        if isinstance(repository_records, dict):
            if "business_pattern_id" in repository_records:
                return [repository_records]
            return list(repository_records.values())

        if isinstance(repository_records, list):
            return repository_records

        return []

    def _validate_records(self, records):
        if not records:
            return False, "no repository records provided"

        for record in records:
            record_dict = self._payload_to_dict(record)
            validation = PatternRepositoryContract.validate(record_dict)
            if not validation.get("valid"):
                return False, validation.get("reason")
        return True, "valid"

    @staticmethod
    def _build_pattern_maturity(total_occurrences):
        if total_occurrences <= 0:
            return 0.0
        return min(1.0, total_occurrences / (total_occurrences + 10.0))

    @staticmethod
    def _build_pattern_stability(success_rates):
        if not success_rates:
            return 0.0
        if len(success_rates) == 1:
            return 1.0
        mean = sum(success_rates) / len(success_rates)
        variance = sum((x - mean) ** 2 for x in success_rates) / len(success_rates)
        stddev = sqrt(variance)
        return max(0.0, 1.0 - min(1.0, stddev / 0.5))

    @staticmethod
    def _build_pattern_strength(success_rate, confidence, average_return):
        strength = success_rate * confidence * (1.0 + average_return)
        return max(0.0, strength)

    def analyze(self, repository_records):
        self.status = "PROCESSING"

        records = self._gather_records(repository_records)
        valid, reason = self._validate_records(records)
        if not valid:
            self.status = "REJECTED"
            return {
                "status": "REJECTED_INPUT",
                "intelligence_status": "INVALID_REPOSITORY_RECORDS",
                "historical_intelligence": None,
                "intelligence_summary": {
                    "valid": False,
                    "reason": reason,
                },
            }

        total_occurrences = 0
        total_wins = 0
        total_losses = 0
        weighted_return = 0.0
        weighted_confidence = 0.0
        success_rates = []

        for record in records:
            record_dict = self._payload_to_dict(record)
            occurrences = self._coerce_int(record_dict.get("occurrences"))
            wins = self._coerce_int(record_dict.get("wins"))
            losses = self._coerce_int(record_dict.get("losses"))
            average_return = self._coerce_float(record_dict.get("average_return"))
            confidence = self._coerce_float(record_dict.get("confidence"))
            success_rate = self._coerce_float(record_dict.get("success_rate"))

            total_occurrences += occurrences
            total_wins += wins
            total_losses += losses
            weighted_return += average_return * occurrences
            weighted_confidence += confidence * occurrences
            success_rates.append(success_rate)

        historical_success_rate = float(total_wins) / total_occurrences if total_occurrences > 0 else 0.0
        historical_average_return = weighted_return / total_occurrences if total_occurrences > 0 else 0.0
        historical_confidence = weighted_confidence / total_occurrences if total_occurrences > 0 else 0.0
        pattern_maturity = self._build_pattern_maturity(total_occurrences)
        pattern_stability = self._build_pattern_stability(success_rates)
        pattern_strength = self._build_pattern_strength(
            historical_success_rate,
            historical_confidence,
            historical_average_return,
        )

        self.status = "ANALYZED"
        historical_intelligence = {
            "historical_occurrences": total_occurrences,
            "historical_success_rate": historical_success_rate,
            "historical_average_return": historical_average_return,
            "historical_confidence": historical_confidence,
            "pattern_maturity": pattern_maturity,
            "pattern_stability": pattern_stability,
            "pattern_strength": pattern_strength,
        }

        intelligence_summary = {
            "records_analyzed": len(records),
            "historical_occurrences": total_occurrences,
            "historical_success_rate": historical_success_rate,
            "historical_average_return": historical_average_return,
            "historical_confidence": historical_confidence,
            "pattern_maturity": pattern_maturity,
            "pattern_stability": pattern_stability,
            "pattern_strength": pattern_strength,
        }

        return {
            "status": "INTELLIGENCE_READY",
            "intelligence_status": "COMPUTED",
            "historical_intelligence": historical_intelligence,
            "intelligence_summary": intelligence_summary,
        }
