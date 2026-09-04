from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd

from .sector_models import NewsItem

POSITIVE = {
    "growth", "order", "contract", "award", "commission", "capacity",
    "investment", "approval", "upgrade", "profit", "earnings", "record",
    "expansion", "renewable", "demand", "recovery", "stimulus",
}
NEGATIVE = {
    "loss", "decline", "downgrade", "penalty", "fine", "investigation",
    "delay", "cancel", "cancellation", "weak", "miss", "warning",
    "default", "cut", "disruption", "sanction", "war", "recession",
}
MAJOR = {
    "order", "contract", "award", "earnings", "profit", "loss",
    "approval", "regulatory", "investigation", "penalty", "tariff",
    "merger", "acquisition", "investment", "guidance", "rating",
}
GLOBAL = {
    "iran", "middle east", "oil", "crude", "brent", "fed", "federal reserve",
    "us rates", "china", "global", "geopolitical", "war", "tariff", "monsoon",
}
DOMESTIC = {
    "india", "government", "rbi", "sebi", "ministry", "budget", "policy",
    "domestic", "rupee", "gst", "capex", "infrastructure",
}
SECTOR_HINTS = {
    "power": {"power", "utilities", "electricity", "renewable", "solar", "grid", "transmission"},
    "energy": {"energy", "oil", "gas", "crude", "renewable"},
    "banking": {"bank", "banking", "rbi", "credit", "loan"},
    "auto": {"auto", "vehicle", "ev", "car", "two-wheeler"},
    "it": {"it", "software", "technology", "tech", "ai", "cloud"},
    "pharma": {"pharma", "drug", "medicine", "healthcare"},
    "metals": {"steel", "metal", "aluminium", "copper", "mining"},
}

def classify_news(
    title: str,
    timestamp=None,
    source: str = "",
    sector_hints: Mapping[str, Iterable[str]] | None = None,
) -> NewsItem:
    text = str(title).lower()
    pos = sum(1 for t in POSITIVE if t in text)
    neg = sum(1 for t in NEGATIVE if t in text)
    direction = "POSITIVE" if pos > neg else ("NEGATIVE" if neg > pos else "NEUTRAL")
    impact = "HIGH" if any(t in text for t in MAJOR) or abs(pos - neg) >= 2 else ("MEDIUM" if pos or neg else "LOW")

    if any(t in text for t in GLOBAL):
        scope = "GLOBAL"
    elif any(t in text for t in DOMESTIC):
        scope = "DOMESTIC"
    else:
        scope = "MARKET"

    hints = sector_hints or SECTOR_HINTS
    sectors = []
    for sector, terms in hints.items():
        if any(term.lower() in text for term in terms):
            sectors.append(sector.upper())

    return NewsItem(
        title=str(title),
        timestamp=pd.to_datetime(timestamp, errors="coerce") if timestamp is not None else None,
        scope=scope,
        direction=direction,
        impact=impact,
        sectors=sectors,
        source=source,
    )

def classify_news_feed(items: Iterable[dict]) -> list[NewsItem]:
    return [
        classify_news(
            item.get("title", ""),
            item.get("timestamp"),
            item.get("source", ""),
        )
        for item in items
        if item.get("title")
    ]
