from __future__ import annotations

from News_Engine.news_intelligence import build_critical_news_events


def _market_map(market_frame):
    if market_frame is None:
        return {}
    try:
        rows = market_frame.to_dict("records")
    except Exception:
        return {}
    result = {}
    for row in rows:
        symbol = str(
            row.get("symbol") or row.get("Symbol") or ""
        ).upper().strip()
        if symbol:
            result[symbol] = row
    return result


def _market_direction(row):
    raw = str(
        row.get("direction")
        or row.get("Direction")
        or row.get("signal")
        or ""
    ).upper()
    if any(x in raw for x in ("BULL", "LONG", "BUY")):
        return "POSITIVE"
    if any(x in raw for x in ("BEAR", "SHORT", "SELL")):
        return "NEGATIVE"
    return "NEUTRAL"


def _news_direction(event):
    text = " ".join(
        [event.get("headline", "")] + event.get("reasons", [])
    ).lower()

    negative = (
        "default", "fraud", "penalty", "investigation", "downgrade",
        "loss", "shutdown", "ban", "delay", "warning", "cut",
    )
    positive = (
        "order", "approval", "acquisition", "partnership", "investment",
        "capacity", "record", "upgrade", "benefit", "buyback",
        "guidance raised", "rate cut",
    )

    neg = sum(x in text for x in negative)
    pos = sum(x in text for x in positive)

    if pos > neg:
        return "POSITIVE"
    if neg > pos:
        return "NEGATIVE"
    return "NEUTRAL"


def build_critical_news_predictions(news_rows, market_frame=None) -> list[dict]:
    events = build_critical_news_events(list(news_rows or []))
    market = _market_map(market_frame)

    predictions = []

    for event in events:
        symbol = event["symbol"]
        nd = _news_direction(event)
        md = _market_direction(market[symbol]) if symbol in market else "NEUTRAL"

        if nd != "NEUTRAL" and md == nd:
            alignment = "ALIGNED"
            state = "CATALYST"
        elif nd != "NEUTRAL" and md != "NEUTRAL" and md != nd:
            alignment = "CONFLICT"
            state = "CONFLICT"
        else:
            alignment = "NOT_CONFIRMED"
            state = "WATCH"

        # A market-confirmed event is promoted in confidence, but the
        # predictor does not modify the underlying SDL signal.
        confidence = float(event["confidence"])
        if alignment == "ALIGNED":
            confidence = min(0.99, confidence + 0.10)

        predictions.append({
            "event_id": event["event_id"],
            "symbol": symbol or "MARKET",
            "sector": event["sector"],
            "state": state,
            "direction": nd,
            "materiality": event["materiality"],
            "catalyst_score": round(
                (1 if nd == "POSITIVE" else -1 if nd == "NEGATIVE" else 0)
                * event["materiality_score"], 4
            ),
            "confidence": round(confidence, 4),
            "headline": event["headline"],
            "reasons": event["reasons"],
            "source_count": event["source_count"],
            "sources": event["sources"],
            "market_alignment": alignment,
            "as_of": event["timestamp"],
        })

    return predictions


# Backward-compatible entry point. It now returns intelligence events rather
# than treating every headline as a candidate prediction.
def build_news_predictions(news, market_frame=None):
    return build_critical_news_predictions(news, market_frame=market_frame)


# ---------------------------------------------------------------------------
# V2.3 MAJOR IMPACT INTELLIGENCE FILTER
# Collect broadly, analyse deeply, display selectively.
# This layer only controls news intelligence presentation.
# ---------------------------------------------------------------------------

_V23_MAJOR_TERMS = (
    "default", "fraud", "investigation", "raid", "arrest", "ban", "debar",
    "penalty", "license cancelled", "licence cancelled", "shutdown", "recall",
    "cyber attack", "ransomware", "major order", "large order", "acquisition",
    "merger", "open offer", "debt restructuring", "insolvency", "bankruptcy",
    "rating downgrade", "guidance cut", "profit warning", "rights issue",
    "buyback", "capacity expansion", "plant shutdown", "production halt",
    "supply disruption", "promoter pledge", "stake sale", "stake increase",
    "regulatory action", "regulatory order", "show cause", "credit rating",
    "earnings warning", "tariff", "sanction", "sanctions", "war"
)

_V23_FALSE_MAJOR_PHRASES = (
    "expected to", "may", "could", "might", "likely to", "plans to",
    "aims to", "seeks to", "proposes", "analysts expect", "market expects",
    "in focus", "watch", "what to watch", "should benefit", "could benefit"
)

_V23_ENTITY_ALIASES = {
    "reliance industries": "RELIANCE", "reliance": "RELIANCE",
    "tata motors": "TATAMOTORS", "tcs": "TCS", "infosys": "INFY",
    "infy": "INFY", "hdfc bank": "HDFCBANK", "icici bank": "ICICIBANK",
    "state bank of india": "SBIN", "sbi": "SBIN",
    "bharti airtel": "BHARTIARTL", "adani enterprises": "ADANIENT",
    "adani ports": "ADANIPORTS",
}

def _v23_text(row):
    if isinstance(row, dict):
        return " ".join(str(row.get(k, "") or "") for k in (
            "headline", "title", "summary", "description", "reasons",
            "event", "impact", "sector"))
    return str(row)

def _v23_resolve_entity(row):
    if not isinstance(row, dict):
        return ""
    raw = str(row.get("symbol") or row.get("entity") or "").strip().upper()
    if raw and raw not in {"MARKET", "N/A", "NONE", "NAN"}:
        return raw
    text = _v23_text(row).lower()
    for alias, symbol in _V23_ENTITY_ALIASES.items():
        if alias in text:
            return symbol
    return ""

def _v23_num_move(row):
    if not isinstance(row, dict):
        return None
    for k in ("price_change_pct", "price_move_pct", "move_pct", "change_pct"):
        try:
            v = row.get(k)
            if v is not None and str(v).strip() not in {"", "nan", "None"}:
                return float(v)
        except Exception:
            pass
    return None

def _v23_major_impact(row):
    text = _v23_text(row).lower()
    entity = _v23_resolve_entity(row)
    materiality = str(row.get("materiality", "") if isinstance(row, dict) else "").upper()
    try:
        sources = int((row.get("source_count", 0) if isinstance(row, dict) else 0) or 0)
    except Exception:
        sources = 0
    move = _v23_num_move(row)
    concrete = [t for t in _V23_MAJOR_TERMS if t in text]
    false_major = [t for t in _V23_FALSE_MAJOR_PHRASES if t in text]

    if false_major and not concrete:
        return {"impact": "NONE", "dashboard_eligible": False, "entity": entity,
                "confidence": 0, "horizon": "N/A",
                "reason": "Editorial/expectation only"}

    if not concrete:
        if materiality == "HIGH" and move is not None and abs(move) >= 1.5 and entity:
            return {"impact": "MAJOR", "dashboard_eligible": True, "entity": entity,
                    "confidence": min(95, 65 + min(20, sources * 5)),
                    "horizon": "INTRADAY",
                    "reason": f"HIGH event + confirmed move {move:.2f}%"}
        return {"impact": "NONE", "dashboard_eligible": False, "entity": entity,
                "confidence": 0, "horizon": "N/A",
                "reason": "No major-impact evidence"}

    if not entity and str(row.get("symbol", "") if isinstance(row, dict) else "").upper() != "MARKET":
        return {"impact": "NONE", "dashboard_eligible": False, "entity": "",
                "confidence": 0, "horizon": "N/A",
                "reason": "Major phrase without resolved entity"}

    confidence = 70
    if materiality == "CRITICAL":
        confidence += 15
    elif materiality == "HIGH":
        confidence += 5
    if sources >= 2:
        confidence += 5
    if move is not None and abs(move) >= 1.5:
        confidence += 5

    return {"impact": "MAJOR", "dashboard_eligible": True, "entity": entity or "MARKET",
            "confidence": min(99, confidence),
            "horizon": "INTRADAY" if move is not None else "EVENT",
            "reason": "Concrete major-impact event: " + ", ".join(concrete[:3])}

def promote_major_impact_news(rows):
    # Return only news events with analysed major market-impact potential.
    if rows is None:
        return []
    try:
        iterable = rows.to_dict("records") if hasattr(rows, "to_dict") else list(rows)
    except Exception:
        iterable = []
    out = []
    for row in iterable:
        if not isinstance(row, dict):
            continue
        result = _v23_major_impact(row)
        item = dict(row)
        item.update({
            "impact": result["impact"],
            "dashboard_eligible": result["dashboard_eligible"],
            "entity": result["entity"],
            "impact_confidence": result["confidence"],
            "impact_horizon": result["horizon"],
            "impact_reason": result["reason"],
        })
        if result["dashboard_eligible"]:
            out.append(item)
    return out
