class HistoricalIntelligenceBridge:

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

    def _validate_intelligence(self, intelligence_output):
        if intelligence_output is None:
            return False, "intelligence_output is None"

        if not isinstance(intelligence_output, dict):
            return False, "intelligence_output must be a dictionary"

        if intelligence_output.get("status") != "INTELLIGENCE_READY":
            return False, "status must be INTELLIGENCE_READY"

        if intelligence_output.get("intelligence_status") != "COMPUTED":
            return False, "intelligence_status must be COMPUTED"

        intelligence = intelligence_output.get("historical_intelligence")
        if not isinstance(intelligence, dict):
            return False, "historical_intelligence must be a dictionary"

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

    def build_intelligence_payload(self, intelligence_output):
        self.status = "PROCESSING"

        payload = self._payload_to_dict(intelligence_output)
        valid, reason = self._validate_intelligence(payload)
        if not valid:
            self.status = "REJECTED"
            return {
                "status": "REJECTED_INPUT",
                "bridge_status": "INVALID_HISTORICAL_INTELLIGENCE",
                "intelligence_payload": None,
                "bridge_summary": {
                    "valid": False,
                    "reason": reason,
                },
            }

        intelligence = payload["historical_intelligence"]
        normalized_payload = {
            "historical_occurrences": self._coerce_int(intelligence.get("historical_occurrences")),
            "historical_success_rate": self._coerce_float(intelligence.get("historical_success_rate")),
            "historical_average_return": self._coerce_float(intelligence.get("historical_average_return")),
            "historical_confidence": self._coerce_float(intelligence.get("historical_confidence")),
            "pattern_maturity": self._coerce_float(intelligence.get("pattern_maturity")),
            "pattern_stability": self._coerce_float(intelligence.get("pattern_stability")),
            "pattern_strength": self._coerce_float(intelligence.get("pattern_strength")),
        }

        self.status = "BRIDGED"
        return {
            "status": "BRIDGE_READY",
            "bridge_status": "PAYLOAD_READY",
            "intelligence_payload": normalized_payload,
            "bridge_summary": {
                "valid": True,
                "historical_occurrences": normalized_payload["historical_occurrences"],
                "historical_success_rate": normalized_payload["historical_success_rate"],
                "historical_average_return": normalized_payload["historical_average_return"],
                "historical_confidence": normalized_payload["historical_confidence"],
                "pattern_maturity": normalized_payload["pattern_maturity"],
                "pattern_stability": normalized_payload["pattern_stability"],
                "pattern_strength": normalized_payload["pattern_strength"],
            },
        }
