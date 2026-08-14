from __future__ import annotations

from typing import Iterable, Optional

from .data_adapter import canonicalize_row
from .signal_engine import build_signal


def replay(rows: Iterable[dict], symbol_key: str = "Symbol") -> list[dict]:
    previous_by_symbol: dict[str, dict] = {}
    results: list[dict] = []

    for raw in rows:
        current = canonicalize_row(raw)
        symbol = str(current.get(symbol_key, current.get("Symbol", ""))).strip().upper()
        previous: Optional[dict] = previous_by_symbol.get(symbol)

        result = build_signal(current, previous)
        results.append(result)

        previous_by_symbol[symbol] = current

    return results
