from __future__ import annotations

from typing import Any

from .engine import RetracementEngine


QUALIFIED_STATES = {
    "STRONG_BULLISH", "STRONG_BEARISH", "STRONG_NEAR_LEVEL",
    "ACTIVE_BULLISH", "ACTIVE_BEARISH", "WAIT_BREAK_CONFIRMATION",
    "DEVELOPING_BULLISH", "DEVELOPING_BEARISH",
}


def is_prequalified(row: dict[str, Any]) -> bool:
    """Boundary check only; this does not calculate or modify SDL ranking."""
    state = str(row.get("decision_state", row.get("opportunity", ""))).strip().upper()
    return state in QUALIFIED_STATES


def process_qualified_pool(engine: RetracementEngine, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run retracement only on the already-qualified pool supplied by SDL."""
    output: list[dict[str, Any]] = []
    for row in rows:
        try:
            if not isinstance(row, dict) or not is_prequalified(row):
                continue
            output.append(engine.process(row))
        except Exception as exc:
            if isinstance(row, dict):
                symbol = row.get("symbol", row.get("Symbol", ""))
                timestamp = row.get("observation_timestamp", "")
            else:
                symbol = ""
                timestamp = ""
            output.append({
                "symbol": symbol,
                "observation_timestamp": timestamp,
                "lifecycle": "ENGINE_ERROR",
                "interaction": "ENGINE_ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            })
    return output
