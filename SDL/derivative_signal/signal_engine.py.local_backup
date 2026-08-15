from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Optional

PRICE_THRESHOLD_PCT = 0.75
PECE_STRONG = 1000.0
PECE_STRONGEST = 2000.0
SR_AT_LEVEL_PCT = 0.50
SR_APPROACHING_PCT = 2.00

BULLISH_FUTURES = {"LB", "LONG", "LONG BUILDUP", "SC", "SHORT COVERING"}
BEARISH_FUTURES = {"SB", "SHORT", "SHORT BUILDUP", "LU", "LONG UNWINDING"}

@dataclass
class SignalResult:
    symbol: str
    direction: str
    price_event: str
    price_change_pct: Optional[float]
    options_structure: str
    options_direction: str
    pece_value: Optional[float]
    futures_buildup: str
    futures_direction: str
    futures_oi_change_pct: Optional[float]
    pcr_change_pct: Optional[float]
    iv_change_pct: Optional[float]
    ivr: Optional[float]
    ivp: Optional[float]
    volume_change_pct: Optional[float]
    oi_change_pct: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    level_distance_pct: Optional[float]
    location: str
    straddle_progress_pct: Optional[float]
    straddle_stage: str
    persistence: str
    bias_category: str
    evidence_state: str
    state: str
    strength: int
    evidence_quality: str
    confirmation_count: int
    conflict_count: int
    reasons: list[str]
    reference_price: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(row: dict[str, Any], *names: str) -> Optional[float]:
    for name in names:
        value = row.get(name)
        if value is None or value == "":
            continue
        try:
            v = float(value)
            if v == v:
                return v
        except (TypeError, ValueError):
            continue
    return None


def _text(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() and str(value).lower() != "nan":
            return str(value).strip().upper()
    return "NOT_AVAILABLE"


def _pece(value: Optional[float]) -> tuple[str, int, str]:
    if value is None:
        return "NOT_AVAILABLE", 0, "NEUTRAL"
    if value >= PECE_STRONGEST:
        return "PE_CE_STRONGEST_BULLISH", 3, "BULLISH"
    if value >= PECE_STRONG:
        return "PE_CE_STRONG_BULLISH", 2, "BULLISH"
    if value > 0:
        return "PE_CE_POSITIVE", 1, "BULLISH"
    if value <= -PECE_STRONGEST:
        return "PE_CE_STRONGEST_BEARISH", 3, "BEARISH"
    if value <= -PECE_STRONG:
        return "PE_CE_STRONG_BEARISH", 2, "BEARISH"
    if value < 0:
        return "PE_CE_NEGATIVE", 1, "BEARISH"
    return "PE_CE_FLAT", 0, "NEUTRAL"


def _stage(progress: Optional[float]) -> str:
    if progress is None:
        return "NOT_AVAILABLE"
    if progress < 25:
        return "EARLY"
    if progress < 50:
        return "DEVELOPING"
    if progress < 75:
        return "ACTIVE"
    if progress < 100:
        return "NEAR_BREAKOUT"
    return "BREAKOUT"


def _srlocation(direction: str, close: Optional[float], support: Optional[float], resistance: Optional[float]):
    if close is None:
        return "NOT_AVAILABLE", None
    if direction == "BULLISH" and resistance not in (None, 0):
        distance = (resistance - close) / close * 100.0
        if distance <= 0:
            return "RESISTANCE_CROSSED", distance
        if distance <= SR_AT_LEVEL_PCT:
            return "AT_RESISTANCE", distance
        if distance <= SR_APPROACHING_PCT:
            return "APPROACHING_RESISTANCE", distance
        return "ROOM_TO_RESISTANCE", distance
    if direction == "BEARISH" and support not in (None, 0):
        distance = (close - support) / close * 100.0
        if distance <= 0:
            return "SUPPORT_BROKEN", distance
        if distance <= SR_AT_LEVEL_PCT:
            return "AT_SUPPORT", distance
        if distance <= SR_APPROACHING_PCT:
            return "APPROACHING_SUPPORT", distance
        return "ROOM_TO_SUPPORT", distance
    return "NOT_AVAILABLE", None


def _progress(row: dict[str, Any]) -> Optional[float]:
    v = _num(row, "straddle_progress_pct", "Straddle Progress %")
    if v is not None:
        return v
    return None


def build_signal(row: dict[str, Any], previous: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    symbol = str(row.get("symbol", row.get("Symbol", ""))).strip().upper()
    close = _num(row, "close", "Close", "price", "Price")

    # Price Chg % is authoritative. Never fall back to Price/Close as if it were a percent.
    price_change = _num(row, "price_chg_pct", "Price Chg %", "Price Chg (%)", "Price_Chg_Pct")
    if price_change is None and previous:
        prev_close = _num(previous, "close", "Close", "price", "Price")
        if close is not None and prev_close not in (None, 0):
            price_change = (close - prev_close) / prev_close * 100.0

    if price_change is None:
        direction = "NEUTRAL"
        price_event = "PRICE_UNAVAILABLE"
    elif price_change >= PRICE_THRESHOLD_PCT:
        direction = "BULLISH"
        price_event = "UP_MOVE_QUALIFIED"
    elif price_change <= -PRICE_THRESHOLD_PCT:
        direction = "BEARISH"
        price_event = "DOWN_MOVE_QUALIFIED"
    else:
        direction = "NEUTRAL"
        price_event = "BELOW_PRICE_GATE"

    pece_value = _num(row, "pe_ce_oi_chg", "Tot PE-CE OI Chg", "PE-CE OI Chg")
    pece_label, pece_strength, pece_direction = _pece(pece_value)

    futures = _text(row, "fut_buildup", "Fut Buildup", "Future Buildup", "Futures Buildup")
    futures_direction = "BULLISH" if futures in BULLISH_FUTURES else "BEARISH" if futures in BEARISH_FUTURES else "NEUTRAL"
    futures_oi = _num(row, "fut_oi_chg_pct", "Fut OI Chg %", "Future OI Chg %", "Futures OI Chg %")

    pcr = _num(row, "pcr_chg_pct", "PCR Chg %")
    iv_change = _num(row, "iv_chg_pct", "IV Chg %")
    ivr = _num(row, "ivr", "IVR")
    ivp = _num(row, "ivp", "IVP")
    volume = _num(row, "volume_chg_pct", "Volume Chg %", "Volume Chg (%)")
    oi_change = _num(row, "oi_chg_pct", "OI Chg %")

    support = _num(row, "support", "Support", "Support Level")
    resistance = _num(row, "resistance", "Resistance", "Resistance Level")
    location, level_distance = _srlocation(direction, close, support, resistance)

    progress = _progress(row)
    stage = _stage(progress)

    confirmations = 0
    conflicts = 0
    reasons: list[str] = []

    if direction != "NEUTRAL":
        if pece_direction == direction:
            confirmations += 2 if pece_strength >= 2 else 1
        elif pece_direction not in {"NEUTRAL", "NOT_AVAILABLE"}:
            conflicts += 2 if pece_strength >= 2 else 1

        if futures_direction == direction:
            confirmations += 1
        elif futures_direction not in {"NEUTRAL", "NOT_AVAILABLE"}:
            conflicts += 1

        if progress is not None:
            if progress >= 75:
                confirmations += 1
            elif progress >= 25:
                confirmations += 0.5

        if location in {"RESISTANCE_CROSSED", "SUPPORT_BROKEN"}:
            confirmations += 1
        elif location in {"AT_RESISTANCE", "AT_SUPPORT"}:
            conflicts += 1

        if volume is not None and volume > 0:
            confirmations += 0.5
        if oi_change is not None and oi_change > 0:
            confirmations += 0.5

    # Evidence state is deliberately separate from directional bias.
    if direction == "NEUTRAL":
        bias = "NEUTRAL / NO SIGNAL"
        evidence_state = "NO SIGNAL"
    elif conflicts >= 2:
        bias = "CONFLICT"
        evidence_state = "CONFLICT"
    elif confirmations >= 3:
        bias = "STRONG BULLISH" if direction == "BULLISH" else "STRONG BEARISH"
        evidence_state = "CONFIRMED"
    elif confirmations >= 1.5:
        bias = "BULLISH" if direction == "BULLISH" else "BEARISH"
        evidence_state = "CONFIRMED"
    elif confirmations >= 0.5:
        bias = "MILD BULLISH" if direction == "BULLISH" else "MILD BEARISH"
        evidence_state = "PARTIAL"
    else:
        bias = "DEVELOPING BULLISH" if direction == "BULLISH" else "DEVELOPING BEARISH"
        evidence_state = "DEVELOPING"

    # Missing core confirmation makes a directional setup incomplete, but only
    # after direction has passed the strict price gate.
    if direction != "NEUTRAL" and pece_value is None and futures_direction == "NEUTRAL" and progress is None:
        bias = "DEVELOPING BULLISH" if direction == "BULLISH" else "DEVELOPING BEARISH"
        evidence_state = "INCOMPLETE"

    if price_change is None:
        bias = "NEUTRAL / NO SIGNAL"
        evidence_state = "INCOMPLETE"

    strength = min(5, int(round(2 + confirmations - conflicts))) if direction != "NEUTRAL" else 0
    strength = max(0, strength)
    if bias == "CONFLICT":
        strength = min(strength, 2)

    evidence_count = sum(v is not None for v in (price_change, pece_value, futures_oi, pcr, iv_change, ivr, ivp, volume, oi_change, support, resistance, progress))
    evidence_quality = "HIGH" if evidence_count >= 8 else "MEDIUM" if evidence_count >= 5 else "LOW"

    if price_change is None:
        reasons.append("Price Chg % is unavailable; no directional signal is issued.")
    else:
        reasons.append(f"Price move {price_change:+.2f}% {'passes' if direction != 'NEUTRAL' else 'does not pass'} the strict +/-{PRICE_THRESHOLD_PCT:.2f}% gate.")
    if pece_value is not None:
        reasons.append(f"PE-CE OI {pece_value:+.0f}: {pece_label}.")
    if futures != "NOT_AVAILABLE":
        reasons.append(f"Futures: {futures}{f' ({futures_oi:+.2f}% OI)' if futures_oi is not None else ''}.")
    if progress is not None:
        reasons.append(f"Straddle progress {progress:.1f}% — {stage}.")
    if location != "NOT_AVAILABLE":
        reasons.append(f"S/R: {location.replace('_', ' ').title()}{f' ({level_distance:+.2f}%)' if level_distance is not None else ''}.")
    if conflicts:
        reasons.append(f"Conflicting evidence count: {conflicts}.")

    state_map = {
        "STRONG BULLISH": "STRONG_BULLISH",
        "STRONG BEARISH": "STRONG_BEARISH",
        "BULLISH": "ACTIVE_BULLISH",
        "BEARISH": "ACTIVE_BEARISH",
        "MILD BULLISH": "MILD_BULLISH",
        "MILD BEARISH": "MILD_BEARISH",
        "DEVELOPING BULLISH": "DEVELOPING_BULLISH",
        "DEVELOPING BEARISH": "DEVELOPING_BEARISH",
        "CONFLICT": "CONFLICT",
        "NEUTRAL / NO SIGNAL": "WATCH",
    }
    state = state_map[bias]

    if location in {"AT_RESISTANCE", "AT_SUPPORT"} and direction != "NEUTRAL" and bias not in {"CONFLICT"}:
        evidence_state = "WAIT LEVEL"

    return SignalResult(
        symbol=symbol,
        direction=direction,
        price_event=price_event,
        price_change_pct=price_change,
        options_structure=pece_label,
        options_direction=pece_direction,
        pece_value=pece_value,
        futures_buildup=futures,
        futures_direction=futures_direction,
        futures_oi_change_pct=futures_oi,
        pcr_change_pct=pcr,
        iv_change_pct=iv_change,
        ivr=ivr,
        ivp=ivp,
        volume_change_pct=volume,
        oi_change_pct=oi_change,
        support=support,
        resistance=resistance,
        level_distance_pct=level_distance,
        location=location,
        straddle_progress_pct=progress,
        straddle_stage=stage,
        persistence="FIRST/UNCONFIRMED",
        bias_category=bias,
        evidence_state=evidence_state,
        state=state,
        strength=strength,
        evidence_quality=evidence_quality,
        confirmation_count=int(round(confirmations)),
        conflict_count=conflicts,
        reasons=reasons,
        reference_price=close,
    ).to_dict()
