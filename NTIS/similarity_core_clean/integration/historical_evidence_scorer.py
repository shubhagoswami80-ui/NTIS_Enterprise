"""
NTIS Historical Evidence Scoring Layer v1.0

Bundle 02 - Historical Intelligence Layer

Calculates evidence strength from HistoricalEvidenceRecord objects.
Designed as an integration layer between historical evidence and
future similarity/probability enhancement.
"""

from similarity_core_clean.integration.historical_evidence_contract import (
    HistoricalEvidenceRecord,
)


class HistoricalEvidenceScorer:

    def __init__(self):
        self.status = "READY"

    def score(self, evidence_records):

        results = []

        for record in evidence_records or []:

            if not isinstance(record, HistoricalEvidenceRecord):
                continue

            score = 0

            if record.ntis_score is not None:
                score += 25

            if record.probability is not None:
                score += 25

            if record.accuracy is not None:
                score += min(float(record.accuracy), 25)

            if record.confidence is not None:
                score += min(float(record.confidence), 25)

            results.append(
                {
                    "symbol": record.symbol,
                    "date": record.date,
                    "evidence_score": score,
                    "status": "SCORED"
                }
            )

        return results
