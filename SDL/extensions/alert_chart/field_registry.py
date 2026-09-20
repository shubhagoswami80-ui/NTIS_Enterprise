from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str  # number, text, boolean, timestamp
    group: str
    aliases: tuple[str, ...] = ()


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("price.current", "Current Price", "number", "Price", ("current_price", "Close", "CMP")),
    FieldSpec("price.open", "Open", "number", "Price", ("opening_price", "Open")),
    FieldSpec("price.high", "High", "number", "Price", ("High",)),
    FieldSpec("price.low", "Low", "number", "Price", ("Low",)),
    FieldSpec("price.change_pct", "Price Change %", "number", "Price", ("price_move_pct", "Price Chg %", "signed_price_move_pct", "Momentum %", "momentum_pct")),
    FieldSpec("straddle.progress_pct", "Straddle Progress %", "number", "Straddle", ("progress", "straddle_progress_pct")),
    FieldSpec("straddle.premium", "Frozen Straddle Premium", "number", "Straddle", ("frozen_straddle",)),
    FieldSpec("straddle.breakout", "Breakout", "boolean", "Straddle", ("factual_breakout",)),
    FieldSpec("straddle.upper_level", "Upper Breakout Level", "number", "Straddle", ("upper_breakout",)),
    FieldSpec("straddle.lower_level", "Lower Breakout Level", "number", "Straddle", ("lower_breakout",)),
    FieldSpec("direction", "Direction", "text", "Decision", ("direction_label",)),
    FieldSpec("strength.value", "Strength", "number", "Decision", ("strength",)),
    FieldSpec("strength.label", "Strength Label", "text", "Decision", ("strength_label",)),
    FieldSpec("stage", "Stage", "text", "Decision", ("stage",)),
    FieldSpec("decision", "Decision", "text", "Decision", ("decision",)),
    FieldSpec("futures.oi_change", "Futures OI Change", "number", "Futures", ("_futures_oi", "futures_oi_chg")),
    FieldSpec("futures.oi_change_pct", "Futures OI Change %", "number", "Futures", ("futures_oi_chg_pct",)),
    FieldSpec("options.ce_oi_change_pct", "CE OI Change %", "number", "Options", ("ce_oi_chg_pct", "Tot CE OI Chg %")),
    FieldSpec("options.pe_oi_change_pct", "PE OI Change %", "number", "Options", ("pe_oi_chg_pct", "Tot PE OI Chg %")),
    FieldSpec("options.pe_ce_oi_change", "PE − CE OI Change", "number", "Options", ("pe_minus_ce_oi_chg", "Tot PE-CE OI Chg")),
    FieldSpec("options.pcr", "PCR", "number", "Options", ("pcr", "PCR", "PCR Value", "pcr_value", "PCR Ratio")),
    FieldSpec("options.pcr_change_pct", "PCR Change %", "number", "Options", ("pcr_chg_pct", "PCR Chg %")),
    FieldSpec("volatility.iv_change_pct", "IV Change %", "number", "Volatility", ("iv_chg_pct", "IV Chg %")),
    FieldSpec("event.first_alert", "First Alert", "boolean", "Events", ("first_alert",)),
    FieldSpec("event.first_breakout", "First Breakout", "boolean", "Events", ("first_breakout",)),
    FieldSpec("event.breakout", "Breakout Event", "boolean", "Events", ("breakout", "factual_breakout")),
    FieldSpec("event.observation_timestamp", "Observation Timestamp", "timestamp", "Events", ("observation_timestamp",)),
)

_BY_KEY = {f.key: f for f in FIELDS}
_BY_ALIAS = {a.lower(): f.key for f in FIELDS for a in f.aliases}


def field_keys() -> list[str]:
    return [f.key for f in FIELDS]


def get_field(key: str) -> FieldSpec:
    if key not in _BY_KEY:
        raise KeyError(f"Unknown alert field: {key}")
    return _BY_KEY[key]


def _nested_get(context: dict[str, Any], path: str) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def resolve_field(context: dict[str, Any], key: str, previous: bool = False) -> Any:
    """Resolve a registered field from current/previous alert contexts."""
    get_field(key)
    root = context.get("previous", {}) if previous else context.get("current", context)
    if not isinstance(root, dict):
        return None

    value = _nested_get(root, key)
    if value is not None:
        return value

    spec = get_field(key)
    for alias in spec.aliases:
        value = _nested_get(root, alias)
        if value is not None:
            return value
    return None
