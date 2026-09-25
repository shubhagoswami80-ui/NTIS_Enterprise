from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from .engine import RSIEngine


def build_rsi_evidence(
    history: Iterable[Any] | None,
    current_timestamp: Any,
    *,
    engine: RSIEngine | None = None,
) -> dict[str, Any]:
    """Return RSI evidence for an already selected stock/snapshot.

    This function is deliberately post-selection. It never receives or changes
    SDL ranking, candidate qualification, signal, or decision gates.
    """
    result = (engine or RSIEngine()).calculate(history, current_timestamp)
    evidence = result.as_dict()

    values = [
        evidence.get("rsi_15m"),
        evidence.get("rsi_30m"),
        evidence.get("rsi_1h"),
        evidence.get("rsi_2h"),
    ]
    valid = [float(v) for v in values if v is not None and pd.notna(v)]
    evidence["rsi_mtf_valid_count"] = len(valid)
    evidence["rsi_mtf_alignment"] = _alignment(evidence)
    evidence["rsi_momentum_state"] = _momentum_state(evidence)
    return evidence


def _alignment(evidence: dict[str, Any]) -> str:
    vals = [
        evidence.get("rsi_15m"), evidence.get("rsi_30m"),
        evidence.get("rsi_1h"), evidence.get("rsi_2h"),
    ]
    vals = [float(v) for v in vals if v is not None and pd.notna(v)]
    if len(vals) < 2:
        return "INSUFFICIENT"
    if all(v >= 50.0 for v in vals):
        return "BULLISH"
    if all(v < 50.0 for v in vals):
        return "BEARISH"
    return "MIXED"


def _momentum_state(evidence: dict[str, Any]) -> str:
    rsi = evidence.get("rsi_15m")
    if rsi is None or pd.isna(rsi):
        return "WARMING UP"
    rsi = float(rsi)
    if rsi >= 70:
        return "STRONG / EXTENDED"
    if rsi >= 50:
        return "POSITIVE"
    if rsi > 30:
        return "NEGATIVE"
    return "WEAK / EXTENDED"
