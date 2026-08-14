from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional


@dataclass
class SignalResult:
    symbol: str
    direction: str
    price_event: str
    oi_evidence: str
    options_structure: str
    location: str
    state: str
    reasons: list[str]
    reference_price: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(row: dict[str, Any], *names: str):
    for name in names:
        value = row.get(name)
        try:
            if value is not None and value != "":
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def build_signal(
    current: dict[str, Any],
    previous: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    symbol = str(current.get("Symbol", current.get("symbol", ""))).strip().upper()

    close = _num(current, "Close", "close", "Current Price", "current_price")
    high = _num(current, "High", "high")
    low = _num(current, "Low", "low")
    prev_high = _num(previous or {}, "High", "high")
    prev_low = _num(previous or {}, "Low", "low")

    price_event = "NO_CHANGE"
    direction = "NEUTRAL"
    reasons: list[str] = []

    if (
        high is not None and prev_high is not None and close is not None
        and high > prev_high and close > prev_high
    ):
        price_event = "HIGH_BREAK_HOLD"
        direction = "BULLISH"
        reasons.append("Current High and Close are above previous High.")
    elif (
        low is not None and prev_low is not None and close is not None
        and low < prev_low and close < prev_low
    ):
        price_event = "LOW_BREAK_HOLD"
        direction = "BEARISH"
        reasons.append("Current Low and Close are below previous Low.")
    elif high is not None and prev_high is not None and high > prev_high:
        price_event = "HIGH_TEST_OR_REJECTION"
        direction = "BULLISH"
        reasons.append("Current High exceeded previous High, but Close did not confirm.")
    elif low is not None and prev_low is not None and low < prev_low:
        price_event = "LOW_TEST_OR_REJECTION"
        direction = "BEARISH"
        reasons.append("Current Low fell below previous Low, but Close did not confirm.")

    oi_change = _num(current, "OI Chg %", "OI_Chg_Pct", "OI Chg")
    if oi_change is None:
        oi_evidence = "UNKNOWN"
    elif oi_change > 0:
        oi_evidence = "PRIMARY_OI_UP"
    elif oi_change < 0:
        oi_evidence = "PRIMARY_OI_DOWN"
    else:
        oi_evidence = "PRIMARY_OI_FLAT"

    if oi_evidence != "UNKNOWN":
        reasons.append(f"Primary OI evidence: {oi_evidence}.")

    pe_ce = _num(current, "Tot PE-CE OI Chg", "PE-CE OI Chg", "PE_CE_OI_Chg")
    if pe_ce is None:
        options_structure = "UNKNOWN"
    elif pe_ce > 0:
        options_structure = "PE_CE_POSITIVE"
    elif pe_ce < 0:
        options_structure = "PE_CE_NEGATIVE"
    else:
        options_structure = "PE_CE_FLAT"

    if options_structure != "UNKNOWN":
        reasons.append(f"PE-CE OI evidence: {options_structure}.")

    resistance = _num(current, "Resistance", "resistance", "Resistance Strike")
    support = _num(current, "Support", "support", "Support Strike")
    location = "UNKNOWN"

    if direction == "BULLISH" and resistance is not None and close is not None:
        location = "RESISTANCE_AHEAD" if resistance >= close else "RESISTANCE_CROSSED"
    elif direction == "BEARISH" and support is not None and close is not None:
        location = "SUPPORT_AHEAD" if support <= close else "SUPPORT_BROKEN"

    if location != "UNKNOWN":
        reasons.append(f"Location: {location}.")

    state = "WATCH"
    if price_event in {"HIGH_BREAK_HOLD", "LOW_BREAK_HOLD"}:
        state = "DEVELOPING" if (
            oi_evidence != "UNKNOWN" or options_structure != "UNKNOWN"
        ) else "WATCH"

    # Location is a trade-decision gate, not a confirmation by itself.
    if location in {"RESISTANCE_AHEAD", "SUPPORT_AHEAD"}:
        state = "NO_TRADE"

    if close is None:
        state = "INSUFFICIENT_DATA"

    return SignalResult(
        symbol=symbol,
        direction=direction,
        price_event=price_event,
        oi_evidence=oi_evidence,
        options_structure=options_structure,
        location=location,
        state=state,
        reasons=reasons,
        reference_price=close,
    ).to_dict()
