import hashlib


class PatternFingerprintEngine:

    def __init__(self):
        self.status = "READY"
        self.fingerprint_version = "1.0"

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _normalize_scalar(value):
        coerced = PatternFingerprintEngine._coerce_float(value)
        if coerced is None:
            return None
        return round(coerced, 6)

    @staticmethod
    def _validate_market_state(market_state):
        if not isinstance(market_state, dict):
            return False, "market_state must be a dictionary"

        required_fields = ["symbol", "date"]
        for field in required_fields:
            if field not in market_state or market_state.get(field) in (None, ""):
                return False, f"missing required field: {field}"

        numeric_fields = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trend",
            "volatility",
            "confidence",
        ]

        has_numeric_payload = False
        for field in numeric_fields:
            if field in market_state and PatternFingerprintEngine._coerce_float(market_state.get(field)) is not None:
                has_numeric_payload = True
                break

        if not has_numeric_payload:
            return False, "market_state must include at least one numeric business field"

        return True, "valid"

    @staticmethod
    def _build_pattern_classification(normalized_features):
        close = normalized_features.get("close")
        open_price = normalized_features.get("open")
        trend = normalized_features.get("trend")
        volatility = normalized_features.get("volatility")

        if close is not None and open_price is not None:
            delta = close - open_price
            if delta > 0:
                direction = "trend_up"
            elif delta < 0:
                direction = "trend_down"
            else:
                direction = "trend_flat"
        elif trend is not None:
            if trend > 0:
                direction = "trend_up"
            elif trend < 0:
                direction = "trend_down"
            else:
                direction = "trend_flat"
        else:
            direction = "trend_unknown"

        if volatility is not None:
            if volatility > 0:
                volatility_label = "volatile"
            else:
                volatility_label = "stable"
        else:
            volatility_label = "unknown"

        return f"{direction}|{volatility_label}"

    @staticmethod
    def _build_pattern_dna(normalized_features):
        ordered = []
        for key in sorted(normalized_features):
            value = normalized_features[key]
            ordered.append(f"{key}={value}")
        return "|".join(ordered)

    @staticmethod
    def _build_business_pattern_id(pattern_classification, pattern_dna):
        material = "|".join([
            str(pattern_classification or ""),
            str(pattern_dna or ""),
        ])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def build_fingerprint(self, market_state):
        valid, message = self._validate_market_state(market_state)
        if not valid:
            return {
                "status": "REJECTED_INPUT",
                "pattern_classification": None,
                "pattern_dna": None,
                "fingerprint_version": self.fingerprint_version,
                "normalized_features": {},
                "validation_message": message,
            }

        normalized_features = {}
        for key in [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trend",
            "volatility",
            "confidence",
        ]:
            if key in market_state:
                if key in {"symbol", "date"}:
                    normalized_features[key] = str(market_state.get(key))
                else:
                    normalized_features[key] = self._normalize_scalar(market_state.get(key))

        pattern_classification = market_state.get("pattern_classification")
        if pattern_classification is None:
            pattern_classification = market_state.get("market_pattern")
        if pattern_classification is None:
            pattern_classification = None

        pattern_dna = self._build_pattern_dna(normalized_features)
        business_pattern_id = self._build_business_pattern_id(pattern_classification, pattern_dna)

        return {
            "status": "FINGERPRINT_READY",
            "pattern_classification": pattern_classification,
            "pattern_dna": pattern_dna,
            "business_pattern_id": business_pattern_id,
            "fingerprint_version": self.fingerprint_version,
            "normalized_features": normalized_features,
        }
