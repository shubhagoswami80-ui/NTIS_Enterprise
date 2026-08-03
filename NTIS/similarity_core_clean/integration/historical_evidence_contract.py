"""
NTIS Historical Evidence Contract v1.0

Bundle 02 - Historical Intelligence Layer

Defines the standard structure exchanged between:
Historical Data Loader
Replay Engine
Similarity Layer
Probability Enhancement
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class HistoricalEvidenceRecord:

    symbol: str
    date: str
    market_pattern: Optional[str] = None
    ntis_score: Optional[float] = None
    probability: Optional[float] = None
    entry: Optional[float] = None
    outcome: Optional[str] = None
    return_pct: Optional[float] = None
    accuracy: Optional[float] = None
    confidence: Optional[float] = None


class HistoricalEvidenceContract:

    REQUIRED_FIELDS = [
        "symbol",
        "date"
    ]

    @staticmethod
    def validate(record):

        missing = []

        for field in HistoricalEvidenceContract.REQUIRED_FIELDS:
            if not getattr(record, field, None):
                missing.append(field)

        return {
            "valid": len(missing) == 0,
            "missing_fields": missing
        }
