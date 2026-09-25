from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .engine import compose_stock_state


def build_stock_state_evidence(
    records: Iterable[Mapping[str, Any]],
    *,
    retracement_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
    rsi_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build a display/evidence table from independently produced layers.

    Inputs are treated as evidence only. No row is removed, ranked, qualified,
    or converted into a trading signal by this integration layer.
    """
    retracement_by_symbol = retracement_by_symbol or {}
    rsi_by_symbol = rsi_by_symbol or {}
    output: list[dict[str, Any]] = []
    for record in records:
        symbol = str(record.get("symbol", record.get("Symbol", ""))).strip()
        state = compose_stock_state(
            record,
            retracement=retracement_by_symbol.get(symbol),
            rsi=rsi_by_symbol.get(symbol),
        )
        output.append(state.as_dict())
    return output
