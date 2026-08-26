from __future__ import annotations

from typing import Any
from pathlib import Path
import pandas as pd

from multi_source_adapter import discover_sources, load_and_merge


PRICE_GATE = 0.75


def _num(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _present(row: dict[str, Any], role: str) -> bool:
    v = row.get(f"_source_{role}")
    return bool(v is True or str(v).strip().lower() in {"true", "1", "yes"})


def _fmt(v: Any, suffix: str = "") -> str:
    n = _num(v)
    return "â€”" if n is None else f"{n:.2f}{suffix}"


def _direction_from_futures(v: Any) -> str:
    text = str(v or "").strip().upper()
    if text in {"LB", "LONG", "LONG BUILDUP", "SC", "SHORT COVERING"}:
        return "BULLISH"
    if text in {"SB", "SHORT", "SHORT BUILDUP", "LU", "LONG UNWINDING"}:
        return "BEARISH"
    return "NEUTRAL"


def _pece_direction(v: Any) -> str:
    n = _num(v)
    if n is None or n == 0:
        return "NEUTRAL"
    return "BULLISH" if n > 0 else "BEARISH"


def _sr_status(direction: str, price: float | None, support: float | None, resistance: float | None) -> str:
    if price is None:
        return "S/R UNAVAILABLE"
    if direction == "BULLISH" and resistance is not None:
        if price >= resistance:
            return "RESISTANCE BROKEN"
        distance = (resistance - price) / price * 100
        if distance <= 0.75:
            return "RESISTANCE TEST"
        if distance <= 2.0:
            return "APPROACHING RESISTANCE"
    if direction == "BEARISH" and support is not None:
        if price <= support:
            return "SUPPORT BROKEN"
        distance = (price - support) / price * 100
        if distance <= 0.75:
            return "SUPPORT TEST"
        if distance <= 2.0:
            return "APPROACHING SUPPORT"
    return "S/R NOT AT IMMEDIATE DECISION LEVEL"


def _first_range_signal(row: dict[str, Any]) -> tuple[str, float | None, float | None]:
    high = _num(row.get("first_snapshot_high", row.get("first_high", row.get("opening_high"))))
    low = _num(row.get("first_snapshot_low", row.get("first_low", row.get("opening_low"))))
    price = _num(row.get("reference_price", row.get("close")))
    if price is None or high is None or low is None:
        return "UNAVAILABLE", high, low
    if price > high:
        return "FIRST-HIGH BROKEN", high, low
    if price < low:
        return "FIRST-LOW BROKEN", high, low
    if price == high:
        return "TESTING FIRST-HIGH", high, low
    if price == low:
        return "TESTING FIRST-LOW", high, low
    return "INSIDE FIRST RANGE", high, low


def _directional_text(direction: str, signal: dict[str, Any]) -> str:
    d = str(direction).upper()
    parts: list[str] = []
    pece = _num(signal.get("pece_value"))
    fut = _direction_from_futures(signal.get("futures_buildup"))
    pcr = _num(signal.get("pcr_change_pct"))
    iv = _num(signal.get("iv_change_pct"))
    vol = _num(signal.get("volume_change_pct"))
    oi = _num(signal.get("oi_change_pct"))

    if pece is not None:
        if (d == "BULLISH" and pece > 0) or (d == "BEARISH" and pece < 0):
            parts.append("PE-CE aligned")
        elif d in {"BULLISH", "BEARISH"}:
            parts.append("PE-CE conflict")
    if fut == d:
        parts.append("Futures aligned")
    elif fut in {"BULLISH", "BEARISH"} and d in {"BULLISH", "BEARISH"}:
        parts.append("Futures conflict")
    if pcr is not None and ((d == "BULLISH" and pcr > 0) or (d == "BEARISH" and pcr < 0)):
        parts.append("PCR aligned")
    if iv is not None and iv > 0:
        parts.append("IV supportive")
    if vol is not None and vol > 0:
        parts.append("Volume active")
    if oi is not None and oi > 0:
        parts.append("OI building")
    return "; ".join(parts) if parts else "Limited directional evidence"


def _developing_direction(
    signal: dict[str, Any],
    row: dict[str, Any],
    sr_status_bull: str,
    sr_status_bear: str,
    first_range_status: str,
) -> tuple[str, int, int, list[str]]:
    """
    Derive a pre-gate directional state from independent evidence families.

    This does NOT override the +/-0.75% gate. It only permits a strong
    developing candidate to be visible before price confirmation.
    """
    votes = {"BULLISH": 0, "BEARISH": 0}
    conflicts = 0
    reasons: list[str] = []

    price = _num(signal.get("price_change_pct"))
    if price is not None and price > 0:
        votes["BULLISH"] += 1
    elif price is not None and price < 0:
        votes["BEARISH"] += 1

    pece_dir = _pece_direction(signal.get("pece_value"))
    if pece_dir in votes:
        votes[pece_dir] += 2
        reasons.append(f"PE-CE {pece_dir.lower()}")

    fut_dir = _direction_from_futures(signal.get("futures_buildup"))
    if fut_dir in votes:
        votes[fut_dir] += 2
        reasons.append(f"Futures {fut_dir.lower()}")

    pcr = _num(signal.get("pcr_change_pct"))
    if pcr is not None and pcr != 0:
        pcr_dir = "BULLISH" if pcr > 0 else "BEARISH"
        votes[pcr_dir] += 1
        reasons.append(f"PCR {pcr_dir.lower()}")

    volume = _num(signal.get("volume_change_pct"))
    oi = _num(signal.get("oi_change_pct"))
    if volume is not None and volume > 0:
        direction = "BULLISH" if price is None or price >= 0 else "BEARISH"
        votes[direction] += 1
        reasons.append("volume active")
    if oi is not None and oi > 0:
        direction = "BULLISH" if price is None or price >= 0 else "BEARISH"
        votes[direction] += 1
        reasons.append("OI building")

    if sr_status_bull == "RESISTANCE BROKEN":
        votes["BULLISH"] += 2
        reasons.append("resistance broken")
    elif sr_status_bear == "SUPPORT BROKEN":
        votes["BEARISH"] += 2
        reasons.append("support broken")

    if first_range_status == "FIRST-HIGH BROKEN":
        votes["BULLISH"] += 2
        reasons.append("first-high broken")
    elif first_range_status == "FIRST-LOW BROKEN":
        votes["BEARISH"] += 2
        reasons.append("first-low broken")

    bull, bear = votes["BULLISH"], votes["BEARISH"]
    if bull == bear or max(bull, bear) < 4:
        return "NEUTRAL", max(bull, bear), min(bull, bear), reasons

    direction = "BULLISH" if bull > bear else "BEARISH"
    conflicts = bear if direction == "BULLISH" else bull
    return direction, max(bull, bear), conflicts, reasons


def _decision_score(
    direction: str,
    price_change: float | None,
    strength: int,
    confirmation_count: int,
    conflict_count: int,
    evidence_quality: str,
    first_range_status: str,
    sr_status: str,
    developing: bool,
) -> tuple[int, str]:
    if direction == "NEUTRAL":
        return 0, "NO DECISION"

    score = max(0, min(5, int(strength or 0))) * 8
    score += min(25, int(confirmation_count or 0) * 5)
    score += {"HIGH": 20, "MEDIUM": 12, "LOW": 5}.get(str(evidence_quality).upper(), 0)

    if (
        (direction == "BULLISH" and first_range_status == "FIRST-HIGH BROKEN")
        or (direction == "BEARISH" and first_range_status == "FIRST-LOW BROKEN")
    ):
        score += 10

    if (
        (direction == "BULLISH" and sr_status == "RESISTANCE BROKEN")
        or (direction == "BEARISH" and sr_status == "SUPPORT BROKEN")
    ):
        score += 10

    score -= min(25, int(conflict_count or 0) * 7)

    if not developing and price_change is not None and abs(price_change) > PRICE_GATE:
        score += min(5, int((abs(price_change) - PRICE_GATE) * 2))

    score = max(0, min(100, int(round(score))))
    if score >= 85:
        label = "VERY STRONG"
    elif score >= 75:
        label = "STRONG"
    elif score >= 60:
        label = "MODERATE"
    elif score >= 45:
        label = "DEVELOPING"
    else:
        label = "WEAK"
    return score, label


def enrich_decision(
    signal: dict[str, Any],
    row: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(signal)
    context = context or {}
    symbol = str(out.get("symbol", row.get("symbol", row.get("Symbol", "")))).strip().upper()
    symbol_context = context.get(symbol, {}) if isinstance(context, dict) else {}
    if not isinstance(symbol_context, dict):
        symbol_context = {}

    decision_context = {**row, **symbol_context}
    decision_context["reference_price"] = out.get("reference_price", row.get("close"))

    price = _num(out.get("reference_price", row.get("close")))
    price_change = _num(out.get("price_change_pct"))
    support = _num(out.get("support"))
    resistance = _num(out.get("resistance"))

    first_range_status, first_high, first_low = _first_range_signal(decision_context)
    sr_using_bull = _sr_status("BULLISH", price, support, resistance)
    sr_using_bear = _sr_status("BEARISH", price, support, resistance)

    gate_direction = str(out.get("direction", "NEUTRAL")).upper()
    developing_direction, vote_strength, vote_conflict, developing_reasons = _developing_direction(
        out, row, sr_using_bull, sr_using_bear, first_range_status
    )

    if gate_direction in {"BULLISH", "BEARISH"}:
        decision_direction = gate_direction
        developing = False
    elif developing_direction in {"BULLISH", "BEARISH"}:
        decision_direction = developing_direction
        developing = True
    else:
        decision_direction = "NEUTRAL"
        developing = False

    sr_status = _sr_status(decision_direction, price, support, resistance)

    confirmation_count = int(out.get("confirmation_count", 0) or 0)
    conflict_count = int(out.get("conflict_count", 0) or 0)

    pece_dir = _pece_direction(out.get("pece_value"))
    fut_dir = _direction_from_futures(out.get("futures_buildup"))
    if decision_direction in {"BULLISH", "BEARISH"}:
        if pece_dir == decision_direction:
            confirmation_count += 1
        elif pece_dir in {"BULLISH", "BEARISH"}:
            conflict_count += 1
        if fut_dir == decision_direction:
            confirmation_count += 2
        elif fut_dir in {"BULLISH", "BEARISH"}:
            conflict_count += 1

        pcr = _num(out.get("pcr_change_pct"))
        if pcr is not None and ((decision_direction == "BULLISH" and pcr > 0) or (decision_direction == "BEARISH" and pcr < 0)):
            confirmation_count += 1

        if sr_status in {"RESISTANCE BROKEN", "SUPPORT BROKEN"}:
            confirmation_count += 2
        elif sr_status in {"RESISTANCE TEST", "SUPPORT TEST"}:
            confirmation_count += 1

        if first_range_status in {"FIRST-HIGH BROKEN", "FIRST-LOW BROKEN"}:
            if (
                (decision_direction == "BULLISH" and first_range_status == "FIRST-HIGH BROKEN")
                or (decision_direction == "BEARISH" and first_range_status == "FIRST-LOW BROKEN")
            ):
                confirmation_count += 2
            else:
                conflict_count += 1

    evidence_count = sum(
        _present(row, role)
        for role in ("BASE", "FUTURES", "IV", "SUPPORT", "RESISTANCE", "VOLUME")
    )
    evidence_quality = "HIGH" if evidence_count >= 5 else "MEDIUM" if evidence_count >= 3 else "LOW"

    base_strength = int(out.get("strength", 0) or 0)
    if developing:
        base_strength = max(1, min(5, int(round(vote_strength / 2))))
    score, score_label = _decision_score(
        decision_direction,
        price_change,
        base_strength,
        confirmation_count,
        conflict_count + (vote_conflict if developing else 0),
        evidence_quality,
        first_range_status,
        sr_status,
        developing,
    )

    gate_passed = (
        (decision_direction == "BULLISH" and price_change is not None and price_change > PRICE_GATE)
        or (decision_direction == "BEARISH" and price_change is not None and price_change < -PRICE_GATE)
    )

    # -----------------------------------------------------------------------
    # CONTROLLED POST-GATE DECISION MATURITY
    # -----------------------------------------------------------------------
    # Gate 1 is absolute: a stock that has not moved beyond +/-0.75% in its
    # established direction is NOT a primary dashboard opportunity. Its
    # evidence remains available internally for replay/audit.
    #
    # Once Gate 1 passes, maturity is decided from the EXISTING evidence
    # already calculated above (S/R, first-range/ORB, Futures, PE-CE, PCR,
    # IV, Volume, OI, confirmations and conflicts). No new source or trading
    # trigger is introduced here.
    #
    # Priority after Gate 1:
    #   1. Material conflict -> NO DECISION
    #   2. Structural level still awaiting break -> WAIT BREAK
    #   3. Strong aligned evidence / actual break -> STRONG
    #   4. Sufficient but not strong -> ACTIVE
    #   5. Relevant evidence building -> DEVELOPING
    # -----------------------------------------------------------------------
    effective_conflicts = conflict_count + (vote_conflict if developing else 0)
    strong_allowed = effective_conflicts == 0

    if not gate_passed:
        decision_state = "NO DECISION"
    elif effective_conflicts >= 2:
        # Opposite evidence is material; suppress the directional entry rather
        # than displaying a misleading bullish/bearish opportunity.
        decision_state = "NO DECISION"
    elif decision_direction == "BULLISH":
        if sr_status in {"RESISTANCE TEST", "APPROACHING RESISTANCE"}:
            # Price gate has passed, but structural confirmation is still
            # pending. This is a genuine post-gate WAIT-BREAK state.
            decision_state = "WAIT_BREAK_CONFIRMATION"
        elif strong_allowed and (
            sr_status == "RESISTANCE BROKEN" or score >= 85
        ):
            decision_state = "STRONG_BULLISH"
        elif score >= 75 and strong_allowed:
            decision_state = "ACTIVE_BULLISH"
        elif (
            score >= 45
            and evidence_quality in {"MEDIUM", "HIGH"}
            and strong_allowed
            and confirmation_count >= 1
        ):
            decision_state = "DEVELOPING_BULLISH"
        else:
            decision_state = "NO DECISION"
    elif decision_direction == "BEARISH":
        if sr_status in {"SUPPORT TEST", "APPROACHING SUPPORT"}:
            # Price gate has passed, but structural confirmation is still
            # pending. This is a genuine post-gate WAIT-BREAK state.
            decision_state = "WAIT_BREAK_CONFIRMATION"
        elif strong_allowed and (
            sr_status == "SUPPORT BROKEN" or score >= 85
        ):
            decision_state = "STRONG_BEARISH"
        elif score >= 75 and strong_allowed:
            decision_state = "ACTIVE_BEARISH"
        elif (
            score >= 45
            and evidence_quality in {"MEDIUM", "HIGH"}
            and strong_allowed
            and confirmation_count >= 1
        ):
            decision_state = "DEVELOPING_BEARISH"
        else:
            decision_state = "NO DECISION"
    else:
        decision_state = "NO DECISION"

    if decision_state == "STRONG_BULLISH":
        if sr_status == "RESISTANCE BROKEN":
            decision_reason = "Resistance breakout confirmed with aligned derivative evidence."
        else:
            decision_reason = "Strong bullish decision with aligned derivative evidence."
    elif decision_state == "ACTIVE_BULLISH":
        decision_reason = (f"Bullish actionability gate passed; derivative evidence has {conflict_count} conflicting signals." if conflict_count > 0 else "Bullish actionability gate passed with aligned derivative evidence.")
    elif decision_state == "STRONG_BEARISH":
        if sr_status == "SUPPORT BROKEN":
            decision_reason = "Support breakdown confirmed with aligned derivative evidence."
        else:
            decision_reason = "Strong bearish decision with aligned derivative evidence."
    elif decision_state == "ACTIVE_BEARISH":
        decision_reason = "Bearish decision confirmed below the actionability gate."
    elif decision_state == "DEVELOPING_BULLISH":
        reason = "; ".join(developing_reasons[:4]) or "directional evidence building"
        decision_reason = f"Developing bullish structure: {reason}."
    elif decision_state == "DEVELOPING_BEARISH":
        reason = "; ".join(developing_reasons[:4]) or "directional evidence building"
        decision_reason = f"Developing bearish structure: {reason}."
    elif decision_state == "WAIT_BREAK_CONFIRMATION":
        decision_reason = f"{sr_status}; waiting for decisive break confirmation."
    else:
        if not gate_passed:
            decision_reason = (
                f"FAILED PRIMARY PRICE GATE — {price_change:+.2f}% "
                f"did not reach +/-{PRICE_GATE:.2f}%"
                if price_change is not None
                else "FAILED PRIMARY PRICE GATE — price change unavailable"
            )
        elif effective_conflicts >= 2:
            decision_reason = (
                "Material opposing evidence; directional decision suppressed "
                "to avoid a wrong entry."
            )
        else:
            decision_reason = "Insufficient aligned post-gate evidence."

    # Keep internal fields for diagnostics; do not expose duplicates in the main card.
    out.update({
        "decision_direction": decision_direction,
        "decision_state": decision_state,
        "gate_passed": bool(gate_passed),
        "sr_status": sr_status,
        "first_range_status": first_range_status,
        "first_range_event": first_range_status,
        "first_snapshot_high": first_high,
        "first_snapshot_low": first_low,
        "decision_quality": evidence_quality,
        "confluence_score": confirmation_count,
        "confirmation_count": confirmation_count,
        "conflict_count": effective_conflicts,
        "decision_score": score,
        "decision_strength": score_label,
        "directional_interpretation": _directional_text(decision_direction, out),
        "futures_interpretation": f"Futures {_direction_from_futures(out.get('futures_buildup'))}",
        "options_interpretation": f"PE-CE {_pece_direction(out.get('pece_value')).lower()}",
        "pcr_interpretation": f"PCR change {_fmt(out.get('pcr_change_pct'), '%')}",
        "iv_interpretation": f"IV change {_fmt(out.get('iv_change_pct'), '%')}",
        "volume_interpretation": f"Volume change {_fmt(out.get('volume_change_pct'), '%')}",
        "sr_interpretation": sr_status,
        "straddle_interpretation": f"Straddle {_fmt(out.get('straddle_progress_pct'), '%')}",
        "decision_reason": decision_reason,
        # Legacy fields retained for compatibility with existing replay/state code.
        "setup": sr_status,
        "confirmation": "CONFIRMED" if gate_passed else "DEVELOPING",
        "action": "DECISION",
        "opportunity": decision_state,
    })
    return out


def merge_evidence(base_path: Path, trading_date: str):
    root = Path(base_path).parent
    bundle = discover_sources(root, trading_date)
    bundle = load_and_merge(bundle)
    if bundle.rows is None:
        return pd.DataFrame(), {}

    source_map = {
        role: str(path)
        for role, path in bundle.files.items()
    }
    return bundle.rows.copy(), source_map

