from __future__ import annotations

from typing import Any

from .field_registry import FIELDS


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _canonicalize(record: dict[str, Any]) -> dict[str, Any]:
    """Map a flat SDL prediction/evidence record into the B3 canonical context."""
    r = dict(record)
    out: dict[str, Any] = dict(r)

    groups = {
        "price": {}, "straddle": {}, "strength": {}, "futures": {},
        "options": {}, "volatility": {}, "event": {},
    }
    for spec in FIELDS:
        value = _first(r, spec.key, *spec.aliases)
        if value is None:
            continue
        parts = spec.key.split(".")
        if len(parts) == 1:
            out[parts[0]] = value
        else:
            groups[parts[0]][parts[1]] = value

    # Preserve explicit values from existing nested records.
    for name, values in groups.items():
        existing = r.get(name)
        if isinstance(existing, dict):
            merged = dict(values)
            merged.update(existing)
            out[name] = merged
        elif values:
            out[name] = values

    return out


def build_context(
    current: dict[str, Any],
    previous: dict[str, Any] | None = None,
    *,
    trading_date: str | None = None,
    observation_timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a replay/LIVE-safe alert context from SDL records.

    The caller supplies authoritative source timestamps. This adapter never
    invents an observation timestamp from the wall clock.
    """
    cur = _canonicalize(current)
    if trading_date is not None:
        cur["trading_date"] = trading_date
    if observation_timestamp is not None:
        cur["observation_timestamp"] = observation_timestamp

    prev = _canonicalize(previous) if previous else {}
    if previous and trading_date is not None:
        prev.setdefault("trading_date", trading_date)

    return {"previous": prev, "current": cur}
