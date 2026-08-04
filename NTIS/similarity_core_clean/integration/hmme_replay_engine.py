"""
NTIS HMME Replay Engine v2.0

Bundle 02 - Historical Intelligence Layer

Adds optional Historical Evidence scoring support
while preserving existing replay contract.
"""

from collections.abc import Iterable

from similarity_core_clean.integration.historical_evidence_contract import (
    HistoricalEvidenceContract,
    HistoricalEvidenceRecord,
)


MAX_REPLAY_MATCHES = 5


class HMMEReplayEngine:

    def __init__(self):
        self.status = "READY"

    @staticmethod
    def _coerce_records(historical_data=None):
        if historical_data is None:
            return []

        if isinstance(historical_data, dict):
            return [historical_data]

        if isinstance(historical_data, Iterable) and not hasattr(historical_data, "columns"):
            return list(historical_data)

        if hasattr(historical_data, "to_dict"):
            try:
                return historical_data.to_dict(orient="records")
            except Exception:
                return []

        return [historical_data]

    @staticmethod
    def _normalize_evidence_record(record):
        if isinstance(record, HistoricalEvidenceRecord):
            return {
                "symbol": record.symbol,
                "date": record.date,
                "market_pattern": record.market_pattern,
                "ntis_score": record.ntis_score,
                "probability": record.probability,
                "entry": record.entry,
                "outcome": record.outcome,
                "return_pct": record.return_pct,
                "accuracy": record.accuracy,
                "confidence": record.confidence,
                "evidence_score": record.confidence,
            }

        if isinstance(record, dict):
            return {
                "symbol": record.get("symbol"),
                "date": record.get("date"),
                "market_pattern": record.get("market_pattern"),
                "ntis_score": record.get("ntis_score"),
                "probability": record.get("probability"),
                "entry": record.get("entry"),
                "outcome": record.get("outcome"),
                "return_pct": record.get("return_pct"),
                "accuracy": record.get("accuracy"),
                "confidence": record.get("confidence"),
                "evidence_score": record.get("evidence_score", record.get("score", record.get("confidence"))),
            }

        return None

    @staticmethod
    def _validate_record(record):
        if record is None:
            return False

        if isinstance(record, dict):
            return bool(record.get("symbol")) and bool(record.get("date"))

        validation = HistoricalEvidenceContract.validate(record)
        return validation.get("valid", False)

    @staticmethod
    def _evidence_score_value(record):
        value = record.get("evidence_score")
        if value is None:
            value = record.get("score")
        if value is None:
            value = record.get("confidence")
        if value is None:
            return None

        try:
            return float(value)
        except Exception:
            return None

    def replay(self, historical_data=None, evidence_scores=None):

        total_records = 0
        if historical_data is not None:
            total_records = len(self._coerce_records(historical_data))

        normalized_scores = []
        for item in evidence_scores or []:
            normalized = self._normalize_evidence_record(item)
            if normalized is None:
                continue

            if not self._validate_record(normalized):
                continue

            score = self._evidence_score_value(normalized)
            if score is None:
                continue

            normalized["evidence_score"] = score
            normalized_scores.append(normalized)

        valid_records = len(normalized_scores)

        ranked_scores = sorted(
            normalized_scores,
            key=lambda item: (-item.get("evidence_score", 0), item.get("symbol", ""), item.get("date", ""))
        )

        average_evidence_score = 0.0
        highest_evidence_score = 0.0
        lowest_evidence_score = 0.0

        if ranked_scores:
            scores = [item.get("evidence_score", 0.0) for item in ranked_scores]
            average_evidence_score = round(sum(scores) / len(scores), 4)
            highest_evidence_score = round(max(scores), 4)
            lowest_evidence_score = round(min(scores), 4)

        matched_records = min(len(ranked_scores), MAX_REPLAY_MATCHES)
        best_matches = ranked_scores[:matched_records]

        replay_confidence = None
        confidence_values = [
            item.get("confidence")
            for item in ranked_scores
            if item.get("confidence") is not None
        ]
        if confidence_values:
            replay_confidence = round(sum(confidence_values) / len(confidence_values), 4)

        replay_summary = {
            "total_records": total_records,
            "valid_records": valid_records,
            "matched_records": matched_records,
            "average_evidence_score": average_evidence_score,
            "highest_evidence_score": highest_evidence_score,
            "lowest_evidence_score": lowest_evidence_score,
            "best_candidates": [
                {
                    "symbol": item.get("symbol"),
                    "date": item.get("date"),
                    "market_pattern": item.get("market_pattern"),
                    "ntis_score": item.get("ntis_score"),
                    "probability": item.get("probability"),
                    "accuracy": item.get("accuracy"),
                    "confidence": item.get("confidence"),
                    "evidence_score": item.get("evidence_score"),
                }
                for item in best_matches
            ],
        }

        return {
            "status": "REPLAY_COMPLETED",
            "records": total_records,
            "valid_records": valid_records,
            "matched_records": matched_records,
            "replay_confidence": replay_confidence,
            "average_evidence_score": average_evidence_score,
            "best_matches": best_matches,
            "replay_summary": replay_summary,
            "evidence_scores": ranked_scores,
        }

    def evaluate(self, replay_result):

        return {
            "status": "EVALUATED",
            "replay": replay_result
        }
