"""
=========================================================
NTIS Historical Similarity Engine
Module : similarity_models.py
Version : 1.0
=========================================================
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

@dataclass(slots=True)
class FeatureVector:
    symbol: str
    ntis_score: float = 0.0
    probability: float = 0.0
    price_change_pct: float = 0.0
    oi_change_pct: float = 0.0
    volume_change_pct: float = 0.0
    pcr: float = 0.0
    ivr: float = 0.0
    ivp: float = 0.0
    pattern: str = ""
    trade_date: Optional[datetime] = None

@dataclass(slots=True)
class HistoricalMatch:
    symbol: str
    historical_date: Optional[datetime]
    similarity_score: float
    outcome: str
    win_probability: float
    ntis_score: float
    confidence: str

@dataclass(slots=True)
class SimilarityResult:
    symbol: str
    similarity: float
    historical_probability: float
    confidence: str
    best_match: Optional[HistoricalMatch] = None
    matches: list[HistoricalMatch] = field(default_factory=list)
    remarks: str = ""

@dataclass(slots=True)
class SimilaritySummary:
    total_symbols: int = 0
    processed_symbols: int = 0
    skipped_symbols: int = 0
    average_similarity: float = 0.0
    average_probability: float = 0.0
    execution_seconds: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)

@dataclass(slots=True)
class SimilarityConfig:
    top_matches: int = 10
    minimum_similarity: float = 60.0
    excellent_match: float = 90.0
    strong_match: float = 80.0
    good_match: float = 70.0
    moderate_match: float = 60.0
    weights: Dict[str, float] = field(default_factory=lambda: {
        "pattern": 0.30,
        "score": 0.20,
        "probability": 0.15,
        "price_oi_volume": 0.20,
        "pcr": 0.10,
        "ivr_ivp": 0.05,
    })
