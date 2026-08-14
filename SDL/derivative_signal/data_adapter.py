from __future__ import annotations

from typing import Any


def canonicalize_row(row: dict[str, Any]) -> dict[str, Any]:
    # Keep the adapter intentionally shallow. It normalizes only names
    # needed by the signal layer and never changes upstream data.
    out = dict(row)
    aliases = {
        "symbol": "Symbol",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
    }
    for source, target in aliases.items():
        if target not in out and source in out:
            out[target] = out[source]
    return out
