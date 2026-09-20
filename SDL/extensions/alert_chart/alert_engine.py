from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable

from .alert_rules import evaluate_rule


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alert_id(rule_id: str, symbol: str, observation_timestamp: str) -> str:
    raw = f"{rule_id}|{symbol}|{observation_timestamp}".encode()
    return hashlib.sha1(raw).hexdigest()[:24]


def evaluate_snapshot(rules: Iterable[dict[str, Any]], context: dict[str, Any], store=None) -> list[dict[str, Any]]:
    """Evaluate enabled rules against one authoritative point-in-time snapshot."""
    current = context.get("current", context)
    symbol = str(current.get("symbol", current.get("Symbol", ""))).strip().upper()
    observation_timestamp = str(current.get("observation_timestamp", ""))
    trading_date = str(current.get("trading_date", ""))
    if not symbol or not observation_timestamp or not trading_date:
        raise ValueError("Alert context requires symbol, trading_date and observation_timestamp")

    events: list[dict[str, Any]] = []
    for rule in rules:
        result = evaluate_rule(rule, context)
        if store is not None and not store.should_emit(
            rule, symbol=symbol, trading_date=trading_date,
            matched=result.matched, observation_timestamp=observation_timestamp,
        ):
            continue
        if not result.matched:
            continue
        event = {
            "alert_id": _alert_id(rule["id"], symbol, observation_timestamp),
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "trading_date": trading_date,
            "symbol": symbol,
            "observation_timestamp": observation_timestamp,
            "direction": current.get("direction"),
            "strength": (current.get("strength", {}).get("value") if isinstance(current.get("strength"), dict) else current.get("strength")),
            "matched_conditions": list(result.reasons),
            "message": " · ".join(result.reasons) if result.reasons else f"{rule.get('name', 'Alert')} triggered",
            "severity": "HIGH" if str(rule.get("name", "")).lower() in {"futures oi spike", "pcr extreme", "strong breakout"} else "INFO",
            "sound": bool(rule.get("sound", False)),
            "payload": current,
            "created_at": _iso_now(),
        }
        if store is None or store.record_event(event):
            events.append(event)
    return events
