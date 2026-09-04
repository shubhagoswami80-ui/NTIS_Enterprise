from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class SectorSnapshot:
    path: Path
    observed_at: pd.Timestamp
    frame: pd.DataFrame
    sector_column: str | None = None
    symbol_column: str | None = None


@dataclass
class NewsItem:
    title: str
    timestamp: pd.Timestamp | None = None
    scope: str = "MARKET"
    direction: str = "NEUTRAL"
    impact: str = "LOW"
    sectors: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class SectorAssessment:
    sector: str
    price_score: float = 0.0
    breadth_score: float = 0.0
    oi_score: float = 0.0
    options_score: float = 0.0
    news_score: float = 0.0
    rotation_score: float = 0.0
    direction: str = "NEUTRAL"
    rotation_state: str = "UNCONFIRMED"
    affected_news: list[NewsItem] = field(default_factory=list)
    leaders: list[dict[str, Any]] = field(default_factory=list)
    laggards: list[dict[str, Any]] = field(default_factory=list)
    intraday_setup: str = "NONE"
    swing_setup: str = "NONE"
    conclusion: str = ""
