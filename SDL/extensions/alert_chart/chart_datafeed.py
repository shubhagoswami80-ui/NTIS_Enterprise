from __future__ import annotations

from typing import Any, Iterable
import pandas as pd


def build_series(rows: Iterable[dict[str, Any]], symbol: str, limit: int = 300) -> list[dict[str, Any]]:
    """Create bounded point-in-time chart data; never scans unbounded history."""
    limit = max(1, min(int(limit), 2000))
    selected = [r for r in rows if str(r.get("symbol", r.get("Symbol", ""))).upper() == symbol.upper()]
    selected = sorted(selected, key=lambda r: str(r.get("observation_timestamp", "")))[-limit:]
    result = []
    for row in selected:
        ts = pd.to_datetime(row.get("observation_timestamp"), errors="coerce")
        price = pd.to_numeric(row.get("current_price", row.get("Close")), errors="coerce")
        if pd.isna(ts) or pd.isna(price):
            continue
        result.append({"time": int(ts.timestamp()), "value": float(price)})
    return result
