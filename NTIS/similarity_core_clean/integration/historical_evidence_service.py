class HistoricalEvidenceService:

    def __init__(self):
        self.status = "READY"

    @staticmethod
    def _payload_to_dict(payload):
        if isinstance(payload, dict):
            return payload
        return {}

    @staticmethod
    def _coerce_int(value):
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value)
        except Exception:
            return None

    def _validate_input(self, evidence_output):
        if evidence_output is None:
            return False, "evidence_output is None"

        if not isinstance(evidence_output, dict):
            return False, "evidence_output must be a dictionary"

        if evidence_output.get("status") != "EVIDENCE_READY":
            return False, "status must be EVIDENCE_READY"

        if evidence_output.get("aggregation_status") != "HISTORICAL_EVIDENCE_AGGREGATED":
            return False, "aggregation_status must be HISTORICAL_EVIDENCE_AGGREGATED"

        evidence = evidence_output.get("historical_evidence")
        if not isinstance(evidence, dict):
            return False, "historical_evidence must be a dictionary"

        required_fields = [
            "historical_occurrences",
            "historical_success_rate",
            "historical_average_return",
            "historical_confidence",
            "pattern_maturity",
            "pattern_stability",
            "pattern_strength",
        ]

        for field in required_fields:
            if field not in evidence:
                return False, f"missing field: {field}"
            if field == "historical_occurrences":
                if self._coerce_int(evidence.get(field)) is None:
                    return False, f"{field} must be an integer"
            else:
                if self._coerce_float(evidence.get(field)) is None:
                    return False, f"{field} must be numeric"

        return True, "valid"

    def serve(self, evidence_output):
        self.status = "PROCESSING"

        payload = self._payload_to_dict(evidence_output)
        valid, reason = self._validate_input(payload)
        if not valid:
            self.status = "REJECTED"
            return {
                "status": "REJECTED_INPUT",
                "service_status": "INVALID_HISTORICAL_EVIDENCE",
                "historical_evidence": None,
                "service_summary": {
                    "valid": False,
                    "reason": reason,
                },
            }

        evidence = payload["historical_evidence"]
        normalized = {
            "historical_occurrences": self._coerce_int(evidence.get("historical_occurrences")),
            "historical_success_rate": self._coerce_float(evidence.get("historical_success_rate")),
            "historical_average_return": self._coerce_float(evidence.get("historical_average_return")),
            "historical_confidence": self._coerce_float(evidence.get("historical_confidence")),
            "pattern_maturity": self._coerce_float(evidence.get("pattern_maturity")),
            "pattern_stability": self._coerce_float(evidence.get("pattern_stability")),
            "pattern_strength": self._coerce_float(evidence.get("pattern_strength")),
        }

        self.status = "SERVING"
        return {
            "status": "SERVICE_READY",
            "service_status": "EVIDENCE_AVAILABLE",
            "historical_evidence": normalized,
            "service_summary": {
                "valid": True,
                **normalized,
            },
        }
