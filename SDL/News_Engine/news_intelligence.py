from __future__ import annotations

"""Critical News Intelligence layer.

Broad discovery is allowed; promotion is deliberately selective.
This module does not alter SDL candidate selection, scoring, PIT, Replay,
First Alert, First Breakout, or Sector Analysis.
"""

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone


ROUTINE_PATTERNS = (
    "trading window", "shareholders meeting", "general updates",
    "integrated filing", "change in auditors", "amendment to aoa",
    "amendment to moa", "press release", "loss of share certificate",
    "loss of certificate", "investor meet", "analyst meet",
    "board meeting", "notice of meeting", "postal ballot",
    "shareholding pattern", "compliance", "secretarial",
)

CRITICAL_PATTERNS = (
    "default", "defaults on", "fraud", "forensic", "investigation",
    "raid", "arrest", "ban", "debar", "penalty", "regulatory action",
    "license cancelled", "licence cancelled", "shutdown", "plant closure",
    "production halt", "recall", "fire", "explosion", "cyber attack",
    "ransomware", "major order", "large order", "order win",
    "acquisition", "merger", "takeover", "open offer", "stake acquisition",
    "fund raise", "fundraising", "debt restructuring", "insolvency",
    "bankruptcy", "credit rating downgrade", "guidance cut",
    "guidance raised", "profit warning", "earnings warning",
    "unexpected loss", "rights issue", "buyback",
)

HIGH_PATTERNS = (
    "order", "contract", "approval", "approved", "capacity expansion",
    "new plant", "commissioned", "production", "earnings", "results",
    "revenue", "profit", "ebitda", "guidance", "stake", "investment",
    "appointment", "resignation", "ceo", "cfo", "md & ceo",
    "tariff", "export ban", "import duty", "policy", "regulation",
    "crude", "oil", "rupee", "interest rate", "rate cut", "rate hike",
    "geopolitical", "sanction", "war", "supply disruption",
)

NEGATIVE_PATTERNS = (
    "default", "fraud", "penalty", "investigation", "downgrade",
    "loss", "weak", "cut", "delay", "ban", "rejected", "shutdown",
    "recall", "warning", "outflow", "miss", "resignation",
)

POSITIVE_PATTERNS = (
    "order win", "major order", "contract win", "approval", "approved",
    "acquisition", "partnership", "investment", "capacity expansion",
    "strong demand", "record", "upgrade", "benefit", "inflow",
    "buyback", "guidance raised", "rate cut",
)

SOURCE_WEIGHTS = {
    "NSE": 1.00,
    "Reuters Discovery": 0.98,
    "Economic Times": 0.90,
    "LiveMint": 0.88,
    "Business Standard": 0.87,
    "Moneycontrol": 0.84,
    "BusinessLine": 0.82,
}


def _text(row: dict) -> str:
    return " ".join(
        str(row.get(k) or "")
        for k in ("title", "summary", "headline")
    ).strip()


def _hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    t = text.lower()
    return [p for p in patterns if p in t]


def classify_materiality(row: dict) -> dict:
    text = _text(row)
    low = text.lower()

    routine = _hits(low, ROUTINE_PATTERNS)
    critical = _hits(low, CRITICAL_PATTERNS)
    high = _hits(low, HIGH_PATTERNS)

    source = str(row.get("source") or "")
    source_weight = SOURCE_WEIGHTS.get(
        source, float(row.get("source_priority") or 0.70)
    )

    # Routine procedural headlines are suppressed unless the same headline
    # contains an explicitly critical event.
    if routine and not critical and not high:
        return {
            "materiality": "SUPPRESS",
            "score": 0.05,
            "reasons": [f"ROUTINE:{x}" for x in routine[:3]],
            "source_weight": source_weight,
        }

    score = 0.15
    reasons = []

    if critical:
        score += 0.60
        reasons.extend(f"CRITICAL:{x}" for x in critical[:4])
    elif high:
        score += 0.35
        reasons.extend(f"HIGH:{x}" for x in high[:4])

    if len(critical) >= 2:
        score += 0.10
    if len(high) >= 2:
        score += 0.05

    score = min(1.0, score * (0.85 + 0.15 * source_weight))

    if score >= 0.72:
        level = "CRITICAL"
    elif score >= 0.42:
        level = "HIGH"
    else:
        level = "CONTEXT"

    return {
        "materiality": level,
        "score": round(score, 4),
        "reasons": reasons[:6],
        "source_weight": round(source_weight, 4),
    }


def _event_key(row: dict) -> str:
    symbol = str(
        row.get("symbol") or row.get("Symbol") or row.get("sector") or "MARKET"
    ).upper().strip()

    title = re.sub(
        r"[^a-z0-9 ]+", " ",
        str(row.get("title") or row.get("headline") or "").lower()
    )
    # Remove common journalistic filler so cross-source versions cluster.
    title = re.sub(
        r"\b(shares?|stock|share price|stocks|today|after|says|report)\b",
        " ",
        title,
    )
    title = re.sub(r"\s+", " ", title).strip()

    # Token signature makes small wording differences less important.
    tokens = sorted(set(title.split()))
    signature = " ".join(tokens[:24])
    return hashlib.sha1(
        f"{symbol}|{signature}".encode("utf-8")
    ).hexdigest()[:20]


def cluster_material_events(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)

    for row in rows:
        m = classify_materiality(row)
        if m["materiality"] == "SUPPRESS":
            continue

        item = dict(row)
        item["materiality"] = m["materiality"]
        item["materiality_score"] = m["score"]
        item["materiality_reasons"] = m["reasons"]
        item["source_weight"] = m["source_weight"]
        groups[_event_key(item)].append(item)

    events = []

    for event_id, items in groups.items():
        items.sort(
            key=lambda x: (
                float(x.get("source_weight") or 0),
                str(x.get("timestamp") or ""),
            ),
            reverse=True,
        )

        sources = sorted({
            str(x.get("source"))
            for x in items
            if x.get("source")
        })

        best = items[0]
        max_score = max(
            float(x.get("materiality_score") or 0)
            for x in items
        )

        if max_score >= 0.72:
            materiality = "CRITICAL"
        elif max_score >= 0.42:
            materiality = "HIGH"
        else:
            materiality = "CONTEXT"

        confirmation_bonus = min(0.18, max(0, len(sources) - 1) * 0.06)
        confidence = min(
            0.98,
            max_score + confirmation_bonus
            + (0.05 if "NSE" in sources else 0),
        )

        event = {
            "event_id": event_id,
            "symbol": str(
                best.get("symbol") or best.get("Symbol") or ""
            ).upper().strip(),
            "sector": str(best.get("sector") or "MARKET"),
            "headline": str(best.get("title") or best.get("headline") or ""),
            "timestamp": str(best.get("timestamp") or ""),
            "materiality": materiality,
            "materiality_score": round(max_score, 4),
            "confidence": round(confidence, 4),
            "source_count": len(sources),
            "sources": sources,
            "source_items": items,
            "reasons": list(dict.fromkeys(
                reason
                for x in items
                for reason in x.get("materiality_reasons", [])
            ))[:8],
        }
        events.append(event)

    rank = {"CRITICAL": 0, "HIGH": 1, "CONTEXT": 2}
    events.sort(
        key=lambda x: (
            rank.get(x["materiality"], 9),
            -float(x["confidence"]),
            x["timestamp"],
        )
    )
    return events


def build_critical_news_events(rows: list[dict]) -> list[dict]:
    """Return only events suitable for the primary intelligence surface."""
    return [
        event
        for event in cluster_material_events(rows)
        if event["materiality"] in {"CRITICAL", "HIGH"}
    ]
