from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class NewsItem:
    title: str
    timestamp: str | None = None
    source: str = ""
    symbol: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

@dataclass
class NewsEvent:
    event_id: str
    title: str
    timestamp: str | None
    source: str
    scope: str
    direction: str
    materiality: str
    sectors: list[str]
    symbols: list[str]
    reason: str
    confidence: float
    raw_items: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class NewsPrediction:
    symbol: str
    sector: str
    state: str
    direction: str
    catalyst_score: float
    confidence: float
    headline: str
    reasons: list[str]
    news_count: int
    market_alignment: str
    as_of: str | None = None

    def as_dict(self):
        return self.__dict__.copy()
