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
    """
    First-snapshot range may be supplied by the replay context.
    Accept several aliases so the decision layer can consume future
    historical/replay implementations without another schema rewrite.
    """
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

    if iv_chg is not None:
        parts.append(f"IV {'supportive' if ((d=='BULLISH' and iv_chg>0) or (d=='BEARISH' and iv_chg>0)) else 'changing'}")
    if vol is not None and vol > 0:
        parts.append("Volume active")
    if oi is not None and oi > 0:
        parts.append("OI building")

    return "; ".join(parts) if parts else "Limited directional evidence"


def enrich_decision(
    signal: dict[str, Any],
    row: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(signal)
    context = context or {}
    direction = str(out.get("direction", "NEUTRAL")).upper()

    price = _num(out.get("reference_price", row.get("close")))
    support = _num(out.get("support"))
    resistance = _num(out.get("resistance"))

    sr_status = _sr_interpretation(direction, price, support, resistance)
    first_range_status, first_high, first_low = _first_range_signal(
        {**row, **context, "reference_price": price}
    )

    confirmations = list(out.get("confirmations_detail", []))
    conflicts = list(out.get("conflicts_detail", []))

    # First-snapshot break is directional evidence, never an automatic trade.
    if direction == "BULLISH" and first_range_status == "FIRST-HIGH BROKEN":
        confirmations.append("FIRST-HIGH BREAK")
    elif direction == "BEARISH" and first_range_status == "FIRST-LOW BROKEN":
        confirmations.append("FIRST-LOW BREAK")
    elif direction == "BULLISH" and first_range_status == "FIRST-LOW BROKEN":
        conflicts.append("FAILED FIRST-RANGE DIRECTION")
    elif direction == "BEARISH" and first_range_status == "FIRST-HIGH BROKEN":
        conflicts.append("FAILED FIRST-RANGE DIRECTION")

    if direction == "BULLISH" and sr_status == "RESISTANCE BROKEN":
        confirmations.append("RESISTANCE BREAK")
    elif direction == "BEARISH" and sr_status == "SUPPORT BROKEN":
        confirmations.append("SUPPORT BREAK")
    elif sr_status in {"RESISTANCE TEST", "SUPPORT TEST"}:
        confirmations.append("S/R TEST")

    confluence = float(out.get("confluence_score", 0) or 0)
    confluence += min(2, len(confirmations))
    confluence -= min(2, len(conflicts))
    confluence = max(0, min(7, confluence))

    source_roles = ["BASE"] if out.get("symbol") else []
    for role in ("FUTURES", "IV", "SUPPORT", "RESISTANCE", "VOLUME"):
        if _present(row, role):
            source_roles.append(role)

    quality = (
        "HIGH" if len(source_roles) >= 5 and len(conflicts) == 0
        else "MEDIUM" if len(source_roles) >= 3 and len(conflicts) <= 1
        else "LOW"
    )

    # Setup classification: keep level interaction and first-range break separate.
    if direction == "NEUTRAL":
        setup = "NO DIRECTION"
        confirmation = "UNCONFIRMED"
        action = "WATCH"
    elif sr_status == "RESISTANCE BROKEN" and direction == "BULLISH":
        setup = "RESISTANCE BREAKOUT"
        confirmation = "CONFIRMED" if confluence >= 5 and not conflicts else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif sr_status == "SUPPORT BROKEN" and direction == "BEARISH":
        setup = "SUPPORT BREAKDOWN"
        confirmation = "CONFIRMED" if confluence >= 5 and not conflicts else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif first_range_status == "FIRST-HIGH BROKEN" and direction == "BULLISH":
        setup = "FIRST-HIGH BREAKOUT"
        confirmation = "CONFIRMED" if confluence >= 4 and not conflicts else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif first_range_status == "FIRST-LOW BROKEN" and direction == "BEARISH":
        setup = "FIRST-LOW BREAKDOWN"
        confirmation = "CONFIRMED" if confluence >= 4 and not conflicts else "DEVELOPING"
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
        confirmation = "CONFIRMED" if confluence >= 4 and not conflicts else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"

    first_range_text = (
        f"First range {first_range_status}"
        + (f" (H {first_high:.2f}, L {first_low:.2f})" if first_high is not None and first_low is not None else "")
    )

    reason = (
        f"{setup}. {sr_status}. {first_range_text}. "
        f"{_directional_text(direction, out)}. "
        f"Evidence quality {quality.lower()}."
    )

    out.update({
        "sr_status": sr_status,
        "first_range_status": first_range_status,
        "first_snapshot_high": first_high,
        "first_snapshot_low": first_low,
        "setup": setup,
        "confirmation": confirmation,
        "action": action,
        "decision_quality": quality,
        "source_roles": source_roles,
        "source_family_count": len(source_roles),
        "confluence_score": int(round(confluence)),
        "directional_interpretation": _directional_text(direction, out),
        "futures_interpretation": f"Futures {out.get('futures_direction','NEUTRAL')} / {out.get('futures_buildup','NOT_AVAILABLE')}",
        "options_interpretation": (
            f"PE-CE OI change {out.get('pece_value','—')}"
            + (" supports direction" if (
                (direction == "BULLISH" and (_num(out.get("pece_value")) or 0) > 0) or
                (direction == "BEARISH" and (_num(out.get("pece_value")) or 0) < 0)
            ) else " is conflicting/neutral")
        ),
        "pcr_interpretation": f"PCR change {_fmt(out.get('pcr_change_pct'), '%')}",
        "iv_interpretation": f"IV change {_fmt(out.get('iv_change_pct'), '%')}",
        "volume_interpretation": f"Volume change {_fmt(out.get('volume_change_pct'), '%')}",
        "sr_interpretation": sr_status,
        "straddle_interpretation": f"Straddle progress {_fmt(out.get('straddle_progress_pct'), '%')} / {out.get('straddle_stage','UNKNOWN')}",
        "decision_reason": reason,
        "opportunity": setup,
        "decision_color": "red" if direction == "BEARISH" else "green" if direction == "BULLISH" else "amber",
    })
    return out


def merge_evidence(base_path, trading_date: str):
    from multi_source_adapter import discover_sources, load_and_merge

    bundle = discover_sources(base_path.parent, trading_date)
    bundle.files["BASE"] = base_path
    bundle = load_and_merge(bundle)

    if bundle.rows is None or bundle.rows.empty:
        raise ValueError(f"No merged source data found for selected snapshot: {base_path}")

    merged = bundle.rows.copy()
    merged["_source_BASE"] = True
    return merged, {"bundle": bundle, "base_path": base_path}
