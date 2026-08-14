from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional


@dataclass
class SignalResult:
    symbol: str
    direction: str
    price_event: str
    futures_position: str
    options_structure: str
    location: str
    state: str
    reasons: list[str]
    reference_price: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(row, *names):
    for name in names:
        value = row.get(name)
        try:
            if value is not None and value != "":
                return float(value)
        except (TypeError, ValueError):
            pass
    return None


def _direction(current, previous):
    if current is None or previous is None:
        return "UNKNOWN"
    if current > previous:
        return "UP"
    if current < previous:
        return "DOWN"
    return "FLAT"


def build_signal(current: dict[str, Any], previous: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    symbol = str(current.get("Symbol", current.get("symbol", ""))).strip().upper()
    close = _num(current, "Close", "close", "Current Price", "current_price")
    high = _num(current, "High", "high")
    low = _num(current, "Low", "low")

    prev_high = _num(previous or {}, "High", "high")
    prev_low = _num(previous or {}, "Low", "low")

    price_event = "NO_CHANGE"
    direction = "NEUTRAL"
    reasons = []

    if high is not None and prev_high is not None and close is not None and high > prev_high and close > prev_high:
        price_event = "HIGH_BREAK_HOLD"
        direction = "BULLISH"
        reasons.append("Current High and Close are above previous High.")
    elif low is not None and prev_low is not None and close is not None and low < prev_low and close < prev_low:
        price_event = "LOW_BREAK_HOLD"
        direction = "BEARISH"
        reasons.append("Current Low and Close are below previous Low.")
    elif high is not None and prev_high is not None and high > prev_high:
        price_event = "HIGH_TEST_OR_REJECTION"
        direction = "BULLISH"
        reasons.append("Current High exceeded previous High, but close did not confirm.")
    elif low is not None and prev_low is not None and low < prev_low:
        price_event = "LOW_TEST_OR_REJECTION"
        direction = "BEARISH"
        reasons.append("Current Low fell below previous Low, but close did not confirm.")

    price_dir = _direction(
        _num(current, "Close", "close", "Current Price", "current_price"),
        _num(previous or {}, "Close", "close", "Current Price", "current_price"),
    )

    oi_now = _num(current, "Futures OI Chg %", "Fut OI Chg %", "Futures_OI_Chg_Pct", "OI Chg %")
    oi_dir = "UP" if oi_now is not None and oi_now > 0 else "DOWN" if oi_now is not None and oi_now < 0 else "FLAT"

    futures_position = "UNKNOWN"
    if price_dir == "UP" and oi_dir == "UP":
        futures_position = "LONG_BUILDUP"
    elif price_dir == "DOWN" and oi_dir == "UP":
        futures_position = "SHORT_BUILDUP"
    elif price_dir == "UP" and oi_dir == "DOWN":
        futures_position = "SHORT_COVERING"
    elif price_dir == "DOWN" and oi_dir == "DOWN":
        futures_position = "LONG_UNWINDING"

    if futures_position != "UNKNOWN":
        reasons.append(f"Futures positioning: {futures_position}.")

    ce = _num(current, "Tot CE OI Chg %", "CE OI Chg %", "CE_OI_Chg_Pct")
    pe = _num(current, "Tot PE OI Chg %", "PE OI Chg %", "PE_OI_Chg_Pct")
    pe_ce = _num(current, "Tot PE-CE OI Chg", "PE-CE OI Chg", "PE_CE_OI_Chg")

    options_structure = "UNKNOWN"
    if pe_ce is not None:
        if pe_ce > 0:
            options_structure = "PE_CE_POSITIVE"
        elif pe_ce < 0:
            options_structure = "PE_CE_NEGATIVE"
        else:
            options_structure = "PE_CE_FLAT"
        reasons.append(f"PE-CE OI change is {options_structure}.")

    resistance = _num(current, "Resistance", "resistance", "Resistance Strike")
    support = _num(current, "Support", "support", "Support Strike")
    location = "UNKNOWN"
    if direction == "BULLISH" and resistance is not None and close is not None and resistance >= close:
        location = "RESISTANCE_AHEAD"
        reasons.append("Resistance is at/above current price.")
    elif direction == "BEARISH" and support is not None and close is not None and support <= close:
        location = "SUPPORT_AHEAD"
        reasons.append("Support is at/below current price.")
    elif close is not None:
        location = "NO_KNOWN_NEARBY_GATE"

    state = "WATCH"
    if price_event in {"HIGH_BREAK_HOLD", "LOW_BREAK_HOLD"} and futures_position != "UNKNOWN":
        state = "DEVELOPING"
    if location in {"RESISTANCE_AHEAD", "SUPPORT_AHEAD"}:
        state = "NO_TRADE"

    if close is None:
        state = "INSUFFICIENT_DATA"

    return SignalResult(
        symbol=symbol,
        direction=direction,
        price_event=price_event,
        futures_position=futures_position,
        options_structure=options_structure,
        location=location,
        state=state,
        reasons=reasons,
        reference_price=close,
    ).to_dict()
