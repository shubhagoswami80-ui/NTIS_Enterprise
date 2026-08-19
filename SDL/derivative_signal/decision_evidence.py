from __future__ import annotations

from typing import Any
import pandas as pd


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


def _fmt(v, suffix=""):
    n = _num(v)
    return "—" if n is None else f"{n:.2f}{suffix}"


def _sr_interpretation(direction, price, support, resistance):
    if price is None:
        return "S/R unavailable"

    if support is not None:
        sd = (price - support) / price * 100.0
        if sd <= 0:
            return "SUPPORT BROKEN" if direction == "BEARISH" else "AT / BELOW SUPPORT"
        if sd <= 0.75:
            return "SUPPORT TEST"
        if sd <= 2.0 and direction == "BEARISH":
            return "APPROACHING SUPPORT"

    if resistance is not None:
        rd = (resistance - price) / price * 100.0
        if rd <= 0:
            return "RESISTANCE BROKEN" if direction == "BULLISH" else "ABOVE RESISTANCE"
        if rd <= 0.75:
            return "RESISTANCE TEST"
        if rd <= 2.0 and direction == "BULLISH":
            return "APPROACHING RESISTANCE"

    return "S/R NOT AT IMMEDIATE DECISION LEVEL"


def _first_range_signal(row: dict[str, Any]) -> tuple[str, float | None, float | None]:
    high = _num(
        row.get("first_snapshot_high")
        if "first_snapshot_high" in row else
        row.get("first_high")
        if "first_high" in row else
        row.get("opening_high")
    )
    low = _num(
        row.get("first_snapshot_low")
        if "first_snapshot_low" in row else
        row.get("first_low")
        if "first_low" in row else
        row.get("opening_low")
    )
    price = _num(row.get("close", row.get("reference_price")))
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
    pece = _num(signal.get("pece_value"))
    fut = str(signal.get("futures_direction", "NEUTRAL")).upper()
    fut_buildup = str(signal.get("futures_buildup", "NOT_AVAILABLE")).upper()
    pcr_chg = _num(signal.get("pcr_change_pct"))
    iv_chg = _num(signal.get("iv_change_pct"))
    vol = _num(signal.get("volume_change_pct"))
    oi = _num(signal.get("oi_change_pct"))

    parts = []
    if d == "BULLISH":
        if pece is not None and pece > 0:
            parts.append("PE-CE supports bullish")
        elif pece is not None and pece < 0:
            parts.append("PE-CE conflicts")
        if fut == "BULLISH":
            parts.append(f"Futures {fut_buildup}")
        elif fut == "BEARISH":
            parts.append("Futures conflicts")
        if pcr_chg is not None and pcr_chg > 0:
            parts.append("PCR improving")
    elif d == "BEARISH":
        if pece is not None and pece < 0:
            parts.append("PE-CE supports bearish")
        elif pece is not None and pece > 0:
            parts.append("PE-CE conflicts")
        if fut == "BEARISH":
            parts.append(f"Futures {fut_buildup}")
        elif fut == "BULLISH":
            parts.append("Futures conflicts")
        if pcr_chg is not None and pcr_chg < 0:
            parts.append("PCR weakening")

    if iv_chg is not None and iv_chg > 0:
        parts.append("IV supportive")
    elif iv_chg is not None:
        parts.append("IV changing")
    if vol is not None and vol > 0:
        parts.append("Volume active")
    if oi is not None and oi > 0:
        parts.append("OI building")

    return "; ".join(parts) if parts else "Limited directional evidence"


def _decision_score(
    direction: str,
    price_change: float | None,
    strength: int,
    confirmation_count: int,
    conflict_count: int,
    evidence_quality: str,
    first_range_status: str,
    sr_status: str,
) -> tuple[int, str]:
    """
    Evidence-strength index used only for ranking/display.

    The strict +/-0.75% eligibility gate remains in signal_engine/dashboard.
    This score does not override eligibility and does not manufacture direction.
    """
    if direction == "NEUTRAL" or price_change is None:
        return 0, "NOT ELIGIBLE"

    # Core signal strength: 0-50.
    score = max(0, min(5, int(strength or 0))) * 10

    # Directional confluence: 0-20.
    score += max(0, min(20, int(confirmation_count or 0) * 4))

    # Evidence quality: 0-15.
    score += {"HIGH": 15, "MEDIUM": 10, "LOW": 4}.get(
        str(evidence_quality).upper(), 0
    )

    # First-range evidence: 0-10.
    if (
        (direction == "BULLISH" and first_range_status == "FIRST-HIGH BROKEN")
        or (direction == "BEARISH" and first_range_status == "FIRST-LOW BROKEN")
    ):
        score += 10
    elif first_range_status in {"TESTING FIRST-HIGH", "TESTING FIRST-LOW"}:
        score += 4

    # Correct S/R break: 0-5.
    if (
        (direction == "BULLISH" and sr_status == "RESISTANCE BROKEN")
        or (direction == "BEARISH" and sr_status == "SUPPORT BROKEN")
    ):
        score += 5

    # Conflicts are a material deduction.
    score -= min(20, int(conflict_count or 0) * 7)

    # Price magnitude is only a tie-break/strength booster.
    if abs(price_change) > 0.75:
        score += min(5, int((abs(price_change) - 0.75) * 2))

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

    # IMPORTANT: dashboard supplies first_range as {SYMBOL: {...}}.
    # Resolve the symbol-specific first range before interpreting it.
    symbol_context = context.get(symbol, {}) if isinstance(context, dict) else {}
    if not isinstance(symbol_context, dict):
        symbol_context = {}
    decision_context = {**row, **symbol_context}
    decision_context["reference_price"] = out.get(
        "reference_price", row.get("close")
    )

    direction = str(out.get("direction", "NEUTRAL")).upper()
    price = _num(out.get("reference_price", row.get("close")))
    support = _num(out.get("support"))
    resistance = _num(out.get("resistance"))

    sr_status = _sr_interpretation(direction, price, support, resistance)
    first_range_status, first_high, first_low = _first_range_signal(decision_context)

    confirmations = list(out.get("reasons", []))
    conflicts = int(out.get("conflict_count", 0) or 0)
    confirmation_count = int(out.get("confirmation_count", 0) or 0)

    if direction == "BULLISH" and first_range_status == "FIRST-HIGH BROKEN":
        confirmation_count += 1
    elif direction == "BEARISH" and first_range_status == "FIRST-LOW BROKEN":
        confirmation_count += 1

    if (
        (direction == "BULLISH" and first_range_status == "FIRST-LOW BROKEN")
        or (direction == "BEARISH" and first_range_status == "FIRST-HIGH BROKEN")
    ):
        conflicts += 1

    if (
        (direction == "BULLISH" and sr_status == "RESISTANCE BROKEN")
        or (direction == "BEARISH" and sr_status == "SUPPORT BROKEN")
    ):
        confirmation_count += 1
    elif sr_status in {"RESISTANCE TEST", "SUPPORT TEST"}:
        confirmation_count += 1

    source_roles = ["BASE"] if symbol else []
    for role in ("FUTURES", "IV", "SUPPORT", "RESISTANCE", "VOLUME"):
        if _present(row, role):
            source_roles.append(role)

    evidence_quality = str(
        out.get("evidence_quality", out.get("decision_quality", "LOW"))
    ).upper()

    if direction == "NEUTRAL":
        setup = "NO DIRECTION"
        confirmation = "UNCONFIRMED"
        action = "WATCH"
    elif sr_status == "RESISTANCE BROKEN" and direction == "BULLISH":
        setup = "RESISTANCE BREAKOUT"
        confirmation = "CONFIRMED" if confirmation_count >= 5 and conflicts == 0 else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif sr_status == "SUPPORT BROKEN" and direction == "BEARISH":
        setup = "SUPPORT BREAKDOWN"
        confirmation = "CONFIRMED" if confirmation_count >= 5 and conflicts == 0 else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif first_range_status == "FIRST-HIGH BROKEN" and direction == "BULLISH":
        setup = "FIRST-HIGH BREAKOUT"
        confirmation = "CONFIRMED" if confirmation_count >= 4 and conflicts == 0 else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif first_range_status == "FIRST-LOW BROKEN" and direction == "BEARISH":
        setup = "FIRST-LOW BREAKDOWN"
        confirmation = "CONFIRMED" if confirmation_count >= 4 and conflicts == 0 else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif sr_status == "RESISTANCE TEST":
        setup = "RESISTANCE BREAKOUT WATCH" if direction == "BULLISH" else "RESISTANCE REVERSAL WATCH"
        confirmation = "BREAKOUT vs REJECTION"
        action = "WAIT"
    elif sr_status == "SUPPORT TEST":
        setup = "SUPPORT REVERSAL WATCH" if direction == "BULLISH" else "SUPPORT BREAKDOWN WATCH"
        confirmation = "BOUNCE vs BREAKDOWN"
        action = "WAIT"
    else:
        setup = "BULLISH CONTINUATION" if direction == "BULLISH" else "BEARISH CONTINUATION"
        confirmation = "CONFIRMED" if confirmation_count >= 4 and conflicts == 0 else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"

    decision_score, decision_strength = _decision_score(
        direction=direction,
        price_change=_num(out.get("price_change_pct")),
        strength=int(out.get("strength", 0) or 0),
        confirmation_count=confirmation_count,
        conflict_count=conflicts,
        evidence_quality=evidence_quality,
        first_range_status=first_range_status,
        sr_status=sr_status,
    )

    first_range_text = (
        f"First range {first_range_status}"
        + (
            f" (H {first_high:.2f}, L {first_low:.2f})"
            if first_high is not None and first_low is not None
            else ""
        )
    )

    reason = (
        f"{setup}. {sr_status}. {first_range_text}. "
        f"{_directional_text(direction, out)}. "
        f"Evidence quality {evidence_quality.lower()}. "
        f"Evidence strength {decision_strength} ({decision_score}/100)."
    )

    out.update({
        "sr_status": sr_status,
        "first_range_status": first_range_status,
        "first_snapshot_high": first_high,
        "first_snapshot_low": first_low,
        "setup": setup,
        "confirmation": confirmation,
        "action": action,
        "decision_quality": evidence_quality,
        "source_roles": source_roles,
        "source_family_count": len(source_roles),
        "confluence_score": confirmation_count,
        "confirmation_count": confirmation_count,
        "conflict_count": conflicts,
        "decision_score": decision_score,
        "decision_strength": decision_strength,
        "directional_interpretation": _directional_text(direction, out),
        "futures_interpretation": (
            f"Futures {out.get('futures_direction','NEUTRAL')} / "
            f"{out.get('futures_buildup','NOT_AVAILABLE')}"
        ),
        "options_interpretation": (
            f"PE-CE OI change {out.get('pece_value','—')}"
            + (
                " supports direction"
                if (
                    (direction == "BULLISH" and (_num(out.get("pece_value")) or 0) > 0)
                    or
                    (direction == "BEARISH" and (_num(out.get("pece_value")) or 0) < 0)
                )
                else " is conflicting/neutral"
            )
        ),
        "pcr_interpretation": f"PCR change {_fmt(out.get('pcr_change_pct'), '%')}",
        "iv_interpretation": f"IV change {_fmt(out.get('iv_change_pct'), '%')}",
        "volume_interpretation": f"Volume change {_fmt(out.get('volume_change_pct'), '%')}",
        "sr_interpretation": sr_status,
        "straddle_interpretation": (
            f"Straddle progress {_fmt(out.get('straddle_progress_pct'), '%')} / "
            f"{out.get('straddle_stage','UNKNOWN')}"
        ),
        "decision_reason": reason,
        "opportunity": setup,
        "decision_color": (
            "red" if direction == "BEARISH"
            else "green" if direction == "BULLISH"
            else "amber"
        ),
    })
    return out


def merge_evidence(base_path, trading_date: str):
    from multi_source_adapter import discover_sources, load_and_merge

    bundle = discover_sources(base_path.parent, trading_date)
    bundle.files["BASE"] = base_path
    bundle = load_and_merge(bundle)

    if bundle.rows is None or bundle.rows.empty:
        raise ValueError(
            f"No merged source data found for selected snapshot: {base_path}"
        )

    merged = bundle.rows.copy()
    merged["_source_BASE"] = True
    return merged, {"bundle": bundle, "base_path": base_path}
