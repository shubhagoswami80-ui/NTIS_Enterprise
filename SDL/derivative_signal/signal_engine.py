from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

PRICE_THRESHOLD_PCT = 0.75
MAG_500 = 500.0
MAG_1000 = 1000.0
MAG_1500 = 1500.0
MAG_2000 = 2000.0
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
    pece_strength_tier: str
    futures_buildup: str
    futures_direction: str
    futures_oi_change: Optional[float]
    futures_oi_change_pct: Optional[float]
    pcr: Optional[float]
    pcr_change_pct: Optional[float]
    iv: Optional[float]
    iv_change_pct: Optional[float]
    ivr: Optional[float]
    ivp: Optional[float]
    volume_change_pct: Optional[float]
    oi_change_pct: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    level_distance_pct: Optional[float]
    location: str
    room_pct: Optional[float]
    straddle_price: Optional[float]
    straddle_progress_pct: Optional[float]
    straddle_stage: str
    momentum: str
    momentum_score: int
    persistence: str
    bias_category: str
    evidence_state: str
    state: str
    strength: int
    strength_label: str
    evidence_quality: str
    confirmation_count: int
    conflict_count: int
    opportunity: str
    action: str
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


def _magnitude(value: Optional[float]) -> tuple[str, int, str]:
    if value is None:
        return "NOT_AVAILABLE", 0, "NEUTRAL"
    if value >= MAG_2000:
        return "2000+", 4, "BULLISH"
    if value >= MAG_1500:
        return "1500-1999", 3, "BULLISH"
    if value >= MAG_1000:
        return "1000-1499", 2, "BULLISH"
    if value >= MAG_500:
        return "500-999", 1, "BULLISH"
    if value > 0:
        return "<500+", 1, "BULLISH"
    if value <= -MAG_2000:
        return "-2000+", 4, "BEARISH"
    if value <= -MAG_1500:
        return "-1500--1999", 3, "BEARISH"
    if value <= -MAG_1000:
        return "-1000--1499", 2, "BEARISH"
    if value <= -MAG_500:
        return "-500--999", 1, "BEARISH"
    if value < 0:
        return "<500-", 1, "BEARISH"
    return "FLAT", 0, "NEUTRAL"


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


def _momentum(direction: str, price_pct: Optional[float], previous: Optional[dict[str, Any]],
              current_progress: Optional[float], volume_pct: Optional[float],
              iv_pct: Optional[float], oi_pct: Optional[float]) -> tuple[str, int]:
    if direction == "NEUTRAL":
        return "STABLE", 0
    score = 0
    previous_price = _num(previous or {}, "price_chg_pct", "Price Chg %")
    if price_pct is not None:
        if abs(price_pct) >= 2.0:
            score += 2
        elif abs(price_pct) >= 1.25:
            score += 1
        if previous_price is not None and ((price_pct > 0) == (previous_price > 0)):
            if abs(price_pct) >= abs(previous_price):
                score += 1
    if current_progress is not None and current_progress >= 50:
        score += 1
    if volume_pct is not None and volume_pct > 0:
        score += 1
    if iv_pct is not None and iv_pct > 0:
        score += 1
    if oi_pct is not None and oi_pct > 0:
        score += 1
    if score >= 5:
        return "STRONG", score
    if score >= 3:
        return "BUILDING", score
    if score >= 1:
        return "STABLE", score
    return "WEAKENING", score


def build_signal(row: dict[str, Any], previous: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    symbol = str(row.get("symbol", row.get("Symbol", ""))).strip().upper()
    close = _num(row, "close", "Close", "price", "Price")

    # Exact percentage field is authoritative. Plain Price/Close is never treated as Price Chg %.
    price_change = _num(row, "price_chg_pct", "Price Chg %", "Price Chg (%)", "Price_Chg_Pct")
    if price_change is None and previous:
        prev_close = _num(previous, "close", "Close", "price", "Price")
        if close is not None and prev_close not in (None, 0):
            price_change = (close - prev_close) / prev_close * 100.0

    if price_change is None:
        direction, price_event = "NEUTRAL", "PRICE_UNAVAILABLE"
    elif price_change >= PRICE_THRESHOLD_PCT:
        direction, price_event = "BULLISH", "UP_MOVE_QUALIFIED"
    elif price_change <= -PRICE_THRESHOLD_PCT:
        direction, price_event = "BEARISH", "DOWN_MOVE_QUALIFIED"
    else:
        direction, price_event = "NEUTRAL", "BELOW_PRICE_GATE"

    pece_value = _num(row, "pe_ce_oi_chg", "Tot PE-CE OI Chg", "PE-CE OI Chg", "PE_CE_OI_Chg")
    pece_label, pece_points, pece_direction = _magnitude(pece_value)

    futures = _text(row, "fut_buildup", "Fut Buildup", "Future Buildup", "Futures Buildup")
    futures_direction = "BULLISH" if futures in BULLISH_FUTURES else "BEARISH" if futures in BEARISH_FUTURES else "NEUTRAL"
    futures_oi = _num(row, "fut_oi_chg", "Fut OI Chg", "Future OI Chg", "Futures OI Chg")
    futures_oi_pct = _num(row, "fut_oi_chg_pct", "Fut OI Chg %", "Future OI Chg %", "Futures OI Chg %")
    futures_tier, futures_points, futures_mag_direction = _magnitude(futures_oi)

    pcr = _num(row, "pcr", "PCR")
    pcr_change = _num(row, "pcr_chg_pct", "PCR Chg %", "PCR Chg (%)")
    iv = _num(row, "iv", "IV", "Implied Volatility", "ATM IV")
    iv_change = _num(row, "iv_chg_pct", "IV Chg %", "IV Chg (%)")
    ivr = _num(row, "ivr", "IVR", "IV Rank")
    ivp = _num(row, "ivp", "IVP", "IV Percentile")
    volume = _num(row, "volume_chg_pct", "Volume Chg %", "Volume Chg (%)")
    oi_change = _num(row, "oi_chg_pct", "OI Chg %", "OI Chg (%)")

    support = _num(row, "support", "Support", "Support Level")
    resistance = _num(row, "resistance", "Resistance", "Resistance Level")
    location, level_distance = _srlocation(direction, close, support, resistance)

    straddle_price = _num(row, "atm_straddle_price", "ATM Straddle Price", "ATM_Straddle_Price")
    progress = _num(row, "straddle_progress_pct", "Straddle Progress %", "ATM Straddle %")
    stage = _stage(progress)
    momentum, momentum_score = _momentum(
        direction, price_change, previous, progress, volume, iv_change, oi_change
    )

    confirmations = 0.0
    conflicts = 0
    reasons: list[str] = []

    if direction != "NEUTRAL":
        # One Options/OI evidence family. Actual magnitude and its percentage are not double-counted.
        if pece_direction == direction:
            confirmations += min(3, pece_points)
        elif pece_direction not in {"NEUTRAL", "NOT_AVAILABLE"}:
            conflicts += min(3, pece_points)

        # One Futures evidence family: buildup + actual OI magnitude + OI % intensity.
        if futures_direction == direction:
            confirmations += 1
            if futures_mag_direction == direction:
                confirmations += min(2, futures_points)
            if futures_oi_pct is not None and futures_oi_pct > 0:
                confirmations += 0.5
        elif futures_direction not in {"NEUTRAL", "NOT_AVAILABLE"}:
            conflicts += 1

        # Contextual evidence: deliberately lower weight than direction-setting families.
        if pcr_change is not None and (
            (direction == "BULLISH" and pcr_change > 0) or
            (direction == "BEARISH" and pcr_change < 0)
        ):
            confirmations += 0.5
        if iv_change is not None and iv_change > 0:
            confirmations += 0.5
        if volume is not None and volume > 0:
            confirmations += 0.5
        if oi_change is not None and oi_change > 0:
            confirmations += 0.5

        # Straddle progression is momentum/opportunity evidence, not direction evidence.
        if progress is not None:
            if progress >= 75:
                confirmations += 1
            elif progress >= 50:
                confirmations += 0.5

        if location in {"RESISTANCE_CROSSED", "SUPPORT_BROKEN"}:
            confirmations += 1
        elif location in {"AT_RESISTANCE", "AT_SUPPORT"}:
            conflicts += 1

    if direction == "NEUTRAL":
        bias, evidence_state = "NEUTRAL / NO SIGNAL", "NO SIGNAL"
    elif conflicts >= 2 and confirmations < 3:
        bias, evidence_state = "CONFLICT", "CONFLICT"
    elif confirmations >= 5:
        bias = "STRONG BULLISH" if direction == "BULLISH" else "STRONG BEARISH"
        evidence_state = "CONFIRMED"
    elif confirmations >= 2.5:
        bias = "BULLISH" if direction == "BULLISH" else "BEARISH"
        evidence_state = "CONFIRMED"
    elif confirmations >= 1:
        bias = "MILD BULLISH" if direction == "BULLISH" else "MILD BEARISH"
        evidence_state = "PARTIAL"
    else:
        bias = "DEVELOPING BULLISH" if direction == "BULLISH" else "DEVELOPING BEARISH"
        evidence_state = "DEVELOPING"

    if direction != "NEUTRAL" and pece_value is None and futures_direction == "NEUTRAL" and progress is None:
        evidence_state = "INCOMPLETE"

    if location in {"AT_RESISTANCE", "AT_SUPPORT"} and direction != "NEUTRAL" and bias != "CONFLICT":
        evidence_state = "WAIT LEVEL"

    strength = 0 if direction == "NEUTRAL" else max(1, min(5, int(round(2 + confirmations - conflicts))))
    if bias == "CONFLICT":
        strength = min(strength, 2)
    strength_label = {
        0: "NONE", 1: "DEVELOPING", 2: "MILD", 3: "MODERATE", 4: "STRONG", 5: "STRONGEST"
    }[strength]

    evidence_count = sum(v is not None for v in (
        price_change, pece_value, futures_oi, futures_oi_pct, pcr, pcr_change,
        iv, iv_change, ivr, ivp, volume, oi_change, support, resistance, progress, straddle_price
    ))
    evidence_quality = "HIGH" if evidence_count >= 11 else "MEDIUM" if evidence_count >= 7 else "LOW"

    if direction == "NEUTRAL":
        opportunity, action = "WATCH", "WATCH"
    elif location in {"AT_RESISTANCE", "AT_SUPPORT"}:
        opportunity, action = "WAIT_LEVEL", "WAIT"
    elif direction == "BULLISH" and location == "RESISTANCE_CROSSED":
        opportunity, action = "BREAKOUT", "ENTER" if strength >= 4 and momentum_score >= 3 else "WAIT"
    elif direction == "BEARISH" and location == "SUPPORT_BROKEN":
        opportunity, action = "BREAKDOWN", "ENTER" if strength >= 4 and momentum_score >= 3 else "WAIT"
    elif progress is not None and progress >= 75:
        opportunity = "PRE_BREAKOUT" if direction == "BULLISH" else "PRE_BREAKDOWN"
        action = "ENTER" if strength >= 4 and momentum_score >= 3 else "WAIT"
    elif strength >= 3:
        opportunity, action = "CONTINUATION", "WATCH" if momentum_score < 2 else "ENTER"
    else:
        opportunity, action = "DEVELOPING", "WATCH"

    reasons.append(
        f"Price move {price_change:+.2f}% {'passes' if direction != 'NEUTRAL' else 'does not pass'} "
        f"the strict +/-{PRICE_THRESHOLD_PCT:.2f}% gate."
        if price_change is not None else "Price Chg % unavailable."
    )
    if pece_value is not None:
        reasons.append(f"PE-CE OI change {pece_value:+.0f}: magnitude {pece_label}.")
    if futures != "NOT_AVAILABLE":
        suffix = ""
        if futures_oi is not None:
            suffix = f", OI {futures_oi:+.0f}"
            if futures_oi_pct is not None:
                suffix += f" ({futures_oi_pct:+.2f}%)"
        reasons.append(f"Futures {futures}{suffix}; tier {futures_tier}.")
    if pcr is not None or pcr_change is not None:
        reasons.append(
            f"PCR {pcr if pcr is not None else '—'}"
            + (f" / change {pcr_change:+.2f}%" if pcr_change is not None else "")
        )
    if iv is not None or iv_change is not None or ivr is not None or ivp is not None:
        reasons.append(
            f"IV {iv if iv is not None else '—'}"
            + (f", change {iv_change:+.2f}%" if iv_change is not None else "")
            + f", IVR {ivr if ivr is not None else '—'}, IVP {ivp if ivp is not None else '—'}."
        )
    if progress is not None:
        reasons.append(f"Straddle progress {progress:.1f}% — {stage}; used for momentum/opportunity, not raw direction.")
    if location != "NOT_AVAILABLE":
        reasons.append(
            f"S/R {location.replace('_', ' ').title()}"
            + (f" ({level_distance:+.2f}% room/distance)." if level_distance is not None else ".")
        )
    reasons.append(f"Momentum {momentum}; strength {strength_label} ({strength}/5).")
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

    return SignalResult(
        symbol=symbol,
        direction=direction,
        price_event=price_event,
        price_change_pct=price_change,
        options_structure=pece_label,
        options_direction=pece_direction,
        pece_value=pece_value,
        pece_strength_tier=pece_label,
        futures_buildup=futures,
        futures_direction=futures_direction,
        futures_oi_change=futures_oi,
        futures_oi_change_pct=futures_oi_pct,
        pcr=pcr,
        pcr_change_pct=pcr_change,
        iv=iv,
        iv_change_pct=iv_change,
        ivr=ivr,
        ivp=ivp,
        volume_change_pct=volume,
        oi_change_pct=oi_change,
        support=support,
        resistance=resistance,
        level_distance_pct=level_distance,
        location=location,
        room_pct=level_distance,
        straddle_price=straddle_price,
        straddle_progress_pct=progress,
        straddle_stage=stage,
        momentum=momentum,
        momentum_score=momentum_score,
        persistence="DEVELOPING" if previous else "FIRST/UNCONFIRMED",
        bias_category=bias,
        evidence_state=evidence_state,
        state=state_map[bias],
        strength=strength,
        strength_label=strength_label,
        evidence_quality=evidence_quality,
        confirmation_count=int(round(confirmations)),
        conflict_count=conflicts,
        opportunity=opportunity,
        action=action,
        reasons=reasons,
        reference_price=close,
    ).to_dict()
