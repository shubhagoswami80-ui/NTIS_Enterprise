class HistoricalEvidenceAggregator:

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

    def _validate_payload(self, payload):
        if payload is None:
            return False, "payload is None"

        if not isinstance(payload, dict):
            return False, "payload must be a dictionary"

        if payload.get("status") != "BRIDGE_READY":
            return False, "status must be BRIDGE_READY"

        if payload.get("bridge_status") != "PAYLOAD_READY":
            return False, "bridge_status must be PAYLOAD_READY"

        intelligence = payload.get("intelligence_payload")
        if not isinstance(intelligence, dict):
            return False, "intelligence_payload must be a dictionary"

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
            if field not in intelligence:
                return False, f"missing field: {field}"
            if field == "historical_occurrences":
                if self._coerce_int(intelligence.get(field)) is None:
                    return False, f"{field} must be an integer"
            else:
                if self._coerce_float(intelligence.get(field)) is None:
                    return False, f"{field} must be numeric"

        return True, "valid"

    def aggregate(self, bridge_payload):
        self.status = "PROCESSING"

        payload = self._payload_to_dict(bridge_payload)
        valid, reason = self._validate_payload(payload)
        if not valid:
            self.status = "REJECTED"
            return {
                "status": "REJECTED_INPUT",
                "aggregation_status": "INVALID_BRIDGE_PAYLOAD",
                "historical_evidence": None,
                "aggregation_summary": {
                    "valid": False,
                    "reason": reason,
                },
            }

        intelligence = payload["intelligence_payload"]
        historical_evidence = {
            "historical_occurrences": self._coerce_int(intelligence.get("historical_occurrences")),
            "historical_success_rate": self._coerce_float(intelligence.get("historical_success_rate")),
            "historical_average_return": self._coerce_float(intelligence.get("historical_average_return")),
            "historical_confidence": self._coerce_float(intelligence.get("historical_confidence")),
            "pattern_maturity": self._coerce_float(intelligence.get("pattern_maturity")),
            "pattern_stability": self._coerce_float(intelligence.get("pattern_stability")),
            "pattern_strength": self._coerce_float(intelligence.get("pattern_strength")),
        }

        self.status = "AGGREGATED"
        return {
            "status": "EVIDENCE_READY",
            "aggregation_status": "HISTORICAL_EVIDENCE_AGGREGATED",
            "historical_evidence": historical_evidence,
            "aggregation_summary": {
                "valid": True,
                **historical_evidence,
            },
        }
