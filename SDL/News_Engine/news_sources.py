from __future__ import annotations

"""NTIS News Engine - multi-source discovery and normalization layer.

Sources are intentionally separated by role:
- NSE corporate announcements: official disclosure / confirmation.
- Economic Times: Indian markets/company coverage.
- LiveMint: Indian markets/company/industry coverage.
- Business Standard: Indian markets/business coverage.
- Moneycontrol: Indian markets/business coverage.
- BusinessLine: Indian business/sector coverage.
- Google News Reuters discovery: global/India market-moving coverage; aggregator only.

The engine stores source provenance and does not alter SDL selection, scoring,
PIT, Replay, First Alert, First Breakout, or Sector Analysis.
"""

import hashlib
import html
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Iterable

try:
    import requests
except Exception:
    requests = None

NSE_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"

RSS_SOURCES = [
    {
        "name": "Economic Times",
        "source_type": "INDIAN_FINANCIAL_MEDIA",
        "url": "https://economictimes.indiatimes.com/markets/stocks/rss.cms",
        "priority": 0.90,
    },
    {
        "name": "LiveMint",
        "source_type": "INDIAN_FINANCIAL_MEDIA",
        "url": "https://www.livemint.com/rss/markets",
        "priority": 0.88,
    },
    {
        "name": "Business Standard",
        "source_type": "INDIAN_FINANCIAL_MEDIA",
        "url": "https://www.business-standard.com/rss/home_page_top_stories.rss",
        "priority": 0.87,
    },
    {
        "name": "Moneycontrol",
        "source_type": "INDIAN_MARKET_MEDIA",
        "url": "https://www.moneycontrol.com/rss/business.xml",
        "priority": 0.84,
    },
    {
        "name": "BusinessLine",
        "source_type": "INDIAN_BUSINESS_MEDIA",
        "url": "https://www.thehindubusinessline.com/feeder/default.rss",
        "priority": 0.82,
    },
]

GOOGLE_NEWS_DISCOVERY = [
    {
        "name": "Reuters Discovery",
        "source_type": "GLOBAL_FINANCIAL_DISCOVERY",
        "query": "India stocks markets economy site:reuters.com",
        "priority": 0.95,
    },
    {
        "name": "Global Markets Discovery",
        "source_type": "GLOBAL_MARKET_DISCOVERY",
        "query": "India markets crude oil rupee rates stocks site:reuters.com",
        "priority": 0.91,
    },
]


def _headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/140 Safari/537.36 NTIS-NewsEngine/2.0"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, application/json, */*",
        "Cache-Control": "no-cache",
    }


def _fetch(url: str, timeout: int = 10) -> bytes:
    if requests is not None:
        r = requests.get(url, headers=_headers(), timeout=timeout)
        r.raise_for_status()
        return r.content
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _strip_html(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _first_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        x = node.find(name)
        if x is not None and x.text:
            return _strip_html(x.text)
    return ""


def _parse_time(node: ET.Element) -> str:
    raw = _first_text(node, ("pubDate", "published", "updated", "date", "dc:date"))
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return raw


def _parse_rss(payload: bytes, source: dict) -> list[dict]:
    root = ET.fromstring(payload)
    rows = []
    for item in root.findall(".//item"):
        title = _first_text(item, ("title",))
        link = _first_text(item, ("link", "guid"))
        summary = _first_text(item, ("description", "summary"))
        if not title:
            continue
        rows.append({
            "title": title,
            "summary": summary,
            "timestamp": _parse_time(item),
            "source": source["name"],
            "source_type": source["source_type"],
            "source_priority": source["priority"],
            "url": link,
            "raw": {"feed": source["url"]},
        })
    return rows


def _google_news_url(query: str) -> str:
    q = urllib.parse.quote(query)
    return (
        "https://news.google.com/rss/search?q="
        + q
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )


def fetch_rss_sources(limit_per_source: int = 30) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    health: list[dict] = []
    for source in RSS_SOURCES:
        started = time.perf_counter()
        try:
            parsed = _parse_rss(_fetch(source["url"]), source)
            parsed = parsed[:max(1, int(limit_per_source))]
            rows.extend(parsed)
            health.append({
                "source": source["name"],
                "status": "OK",
                "rows": len(parsed),
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            })
        except Exception as exc:
            health.append({
                "source": source["name"],
                "status": "ERROR",
                "rows": 0,
                "error": str(exc)[:240],
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            })
    return rows, health


def fetch_global_discovery(limit_per_query: int = 20) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    health: list[dict] = []
    for source in GOOGLE_NEWS_DISCOVERY:
        started = time.perf_counter()
        try:
            source_cfg = {
                "name": source["name"],
                "source_type": source["source_type"],
                "url": _google_news_url(source["query"]),
                "priority": source["priority"],
            }
            parsed = _parse_rss(_fetch(source_cfg["url"]), source_cfg)
            parsed = parsed[:max(1, int(limit_per_query))]
            rows.extend(parsed)
            health.append({
                "source": source["name"],
                "status": "OK",
                "rows": len(parsed),
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            })
        except Exception as exc:
            health.append({
                "source": source["name"],
                "status": "ERROR",
                "rows": 0,
                "error": str(exc)[:240],
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            })
    return rows, health


def fetch_normalized_nse_news(limit: int = 30) -> list[dict]:
    """Backward-compatible official NSE source adapter."""
    try:
        payload = _fetch(NSE_URL)
        data = __import__("json").loads(payload.decode("utf-8"))
    except Exception:
        return []

    if isinstance(data, dict):
        data = data.get("data") or data.get("results") or []
    rows = []
    for item in data[:max(1, int(limit))]:
        rows.append({
            "title": _strip_html(
                item.get("desc")
                or item.get("subject")
                or item.get("title")
                or item.get("headline")
                or ""
            ),
            "summary": "",
            "timestamp": (
                item.get("an_dt")
                or item.get("timestamp")
                or item.get("date")
                or datetime.now(timezone.utc).isoformat()
            ),
            "source": "NSE",
            "source_type": "OFFICIAL_DISCLOSURE",
            "source_priority": 1.00,
            "url": item.get("attchmntFile") or item.get("url") or "",
            "symbol": item.get("symbol") or item.get("sm_name") or "",
            "raw": item,
        })
    return rows


def _dedup_key(row: dict) -> str:
    title = re.sub(r"[^a-z0-9]+", " ", str(row.get("title", "")).lower()).strip()
    return hashlib.sha1(title.encode("utf-8")).hexdigest()


def fetch_multi_source_news(
    limit_per_source: int = 25,
    include_nse: bool = True,
    include_global: bool = True,
) -> tuple[list[dict], list[dict]]:
    """Fetch all enabled sources and return deduplicated normalized headlines.

    Deduplication is headline-based at this stage. Event-level deduplication,
    entity mapping and materiality remain owned by news_intelligence.py.
    """
    rows: list[dict] = []
    health: list[dict] = []

    if include_nse:
        started = time.perf_counter()
        nse = fetch_normalized_nse_news(limit_per_source)
        rows.extend(nse)
        health.append({
            "source": "NSE",
            "status": "OK" if nse else "EMPTY",
            "rows": len(nse),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        })

    rss_rows, rss_health = fetch_rss_sources(limit_per_source)
    rows.extend(rss_rows)
    health.extend(rss_health)

    if include_global:
        global_rows, global_health = fetch_global_discovery(limit_per_source)
        rows.extend(global_rows)
        health.extend(global_health)

    # Suppress exact duplicates from the same source only.  Do NOT collapse
    # identical headlines across different sources here: cross-source
    # confirmation is deliberately preserved for event clustering.
    unique = {}
    for row in rows:
        key = (str(row.get("source") or ""), _dedup_key(row))
        current = unique.get(key)
        if current is None or str(row.get("timestamp", "")) > str(current.get("timestamp", "")):
            unique[key] = row

    result = sorted(
        unique.values(),
        key=lambda x: str(x.get("timestamp", "")),
        reverse=True,
    )
    return result, health
