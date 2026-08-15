from __future__ import annotations

from typing import Any
import pandas as pd

SOURCE_LABELS = {
    "BASE": "Price/OI", "FUTURES": "Futures", "IV": "IV",
    "SUPPORT": "Support", "RESISTANCE": "Resistance", "VOLUME": "Volume",
}


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


def _sr_interpretation(direction, price, support, resistance, price_change):
    if price is None:
        return "S/R unavailable"

    if support is not None:
        sd = (price - support) / price * 100
        if sd <= 0:
            if direction == "BEARISH":
                return "SUPPORT BROKEN - breakdown risk"
            return "AT / BELOW SUPPORT - reversal evidence required"
        if sd <= 0.75:
            if direction == "BULLISH":
                return "SUPPORT TEST - bullish reversal candidate"
            return "AT SUPPORT - breakdown/reversal decision point"

    if resistance is not None:
        rd = (resistance - price) / price * 100
        if rd <= 0:
            if direction == "BULLISH":
                return "RESISTANCE BROKEN - breakout confirmation required"
            return "ABOVE RESISTANCE - reversal risk if rejected"
        if rd <= 0.75:
            if direction == "BEARISH":
                return "RESISTANCE TEST - bearish reversal candidate"
            return "AT RESISTANCE - breakout/rejection decision point"
        if rd <= 2.0:
            return "APPROACHING RESISTANCE"
    return "S/R not at immediate decision level"


def _directional_interpretation(signal):
    d = str(signal.get("direction", "NEUTRAL")).upper()
    pece = _num(signal.get("pece_value"))
    fut = str(signal.get("futures_direction", "NEUTRAL")).upper()
    pcr = _num(signal.get("pcr_change_pct"))
    iv = _num(signal.get("iv_change_pct"))
    vol = _num(signal.get("volume_change_pct"))
    oi = _num(signal.get("oi_change_pct"))

    parts = []
    if d == "BULLISH":
        if pece is not None and pece > 0: parts.append("PE-CE supports bullish")
        if pece is not None and pece < 0: parts.append("PE-CE conflicts")
        if fut == "BULLISH": parts.append("Futures confirms")
        if fut == "BEARISH": parts.append("Futures conflicts")
        if pcr is not None and pcr > 0: parts.append("PCR improving")
    elif d == "BEARISH":
        if pece is not None and pece < 0: parts.append("PE-CE supports bearish")
        if pece is not None and pece > 0: parts.append("PE-CE conflicts")
        if fut == "BEARISH": parts.append("Futures confirms")
        if fut == "BULLISH": parts.append("Futures conflicts")
        if pcr is not None and pcr < 0: parts.append("PCR weakening")
    if iv is not None and iv > 0: parts.append("IV expanding")
    if vol is not None and vol > 0: parts.append("Volume active")
    if oi is not None and oi > 0: parts.append("OI building")
    return "; ".join(parts) if parts else "Limited directional evidence"


def enrich_decision(signal: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = dict(signal)
    direction = str(out.get("direction", "NEUTRAL")).upper()

    price = _num(out.get("reference_price"))
    support = _num(out.get("support"))
    resistance = _num(out.get("resistance"))
    price_change = _num(out.get("price_change_pct"))

    # IMPORTANT: row is CURRENT merged evidence, not previous snapshot.
    source_roles = ["BASE"] if out.get("symbol") else []
    for role in SOURCE_LABELS:
        if role != "BASE" and _present(row, role):
            source_roles.append(role)

    missing = [r for r in ("FUTURES", "IV", "SUPPORT", "RESISTANCE", "VOLUME") if r not in source_roles]

    sr_status = _sr_interpretation(direction, price, support, resistance, price_change)
    sr_distance = None
    if direction == "BULLISH" and resistance not in (None, 0) and price is not None:
        sr_distance = (resistance - price) / price * 100
    elif direction == "BEARISH" and support not in (None, 0) and price is not None:
        sr_distance = (price - support) / price * 100

    confirmations = list(out.get("confirmations_detail", []))
    conflicts = list(out.get("conflicts_detail", []))

    if "RESISTANCE BROKEN" in sr_status and direction == "BULLISH":
        confirmations.append("RESISTANCE BREAK")
    if "SUPPORT BROKEN" in sr_status and direction == "BEARISH":
        confirmations.append("SUPPORT BREAK")
    if "TEST" in sr_status:
        confirmations.append("S/R TEST")

    confluence = int(round(float(out.get("confluence_score", 0) or 0)))
    confluence = max(0, min(5, confluence + (1 if confirmations else 0) - (1 if conflicts else 0)))

    quality = "HIGH" if len(source_roles) >= 5 and not conflicts else "MEDIUM" if len(source_roles) >= 3 else "LOW"

    # Explicit setup/action vocabulary: the dashboard is a decision surface.
    if direction == "NEUTRAL":
        setup, action, confirmation = "NO DIRECTION", "WATCH", "UNCONFIRMED"
    elif "RESISTANCE BROKEN" in sr_status and direction == "BULLISH":
        setup = "RESISTANCE BREAKOUT"
        confirmation = "CONFIRMED" if confluence >= 4 and not conflicts else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif "SUPPORT BROKEN" in sr_status and direction == "BEARISH":
        setup = "SUPPORT BREAKDOWN"
        confirmation = "CONFIRMED" if confluence >= 4 and not conflicts else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"
    elif "AT RESISTANCE" in sr_status:
        setup = "RESISTANCE TEST"
        confirmation = "REVERSAL / BREAKOUT DECISION"
        action = "WAIT"
    elif "AT SUPPORT" in sr_status:
        setup = "SUPPORT TEST"
        confirmation = "REVERSAL / BREAKDOWN DECISION"
        action = "WAIT"
    elif "APPROACHING RESISTANCE" in sr_status:
        setup = "APPROACHING RESISTANCE"
        confirmation = "BREAKOUT DEVELOPING"
        action = "WAIT"
    else:
        setup = "BULLISH CONTINUATION" if direction == "BULLISH" else "BEARISH CONTINUATION"
        confirmation = "CONFIRMED" if confluence >= 4 and not conflicts else "DEVELOPING"
        action = "ENTER / CONTINUE" if confirmation == "CONFIRMED" else "WAIT FOR CONFIRMATION"

    # Reversal candidate language is allowed before confirmation.
    if "TEST" in sr_status and not conflicts:
        if direction == "BULLISH":
            setup = "SUPPORT REVERSAL CANDIDATE"
        elif direction == "BEARISH":
            setup = "RESISTANCE REVERSAL CANDIDATE"

    decision_reason = (
        f"{setup}. {sr_status}. "
        f"{_directional_interpretation(out)}. "
        f"Evidence quality {quality.lower()}."
    )

    out.update({
        "sr_status": sr_status,
        "sr_distance_pct": sr_distance,
        "setup": setup,
        "confirmation": confirmation,
        "action": action,
        "decision_quality": quality,
        "source_roles": source_roles,
        "missing_source_roles": missing,
        "source_family_count": len(source_roles),
        "confluence_score": confluence,
        "decision_reason": decision_reason,
        "directional_interpretation": _directional_interpretation(out),
        "futures_interpretation": f"Futures {out.get('futures_direction','NEUTRAL')}",
        "options_interpretation": (
            "PE-CE supports direction" if (
                (direction == "BULLISH" and (_num(out.get("pece_value")) or 0) > 0) or
                (direction == "BEARISH" and (_num(out.get("pece_value")) or 0) < 0)
            ) else "PE-CE neutral/conflicting"
        ),
        "pcr_interpretation": (
            f"PCR change {_fmt(out.get('pcr_change_pct'), '%')}"
        ),
        "iv_interpretation": f"IV change {_fmt(out.get('iv_change_pct'), '%')}",
        "volume_interpretation": f"Volume change {_fmt(out.get('volume_change_pct'), '%')}",
        "sr_interpretation": sr_status,
        "straddle_interpretation": (
            f"Straddle {_fmt(out.get('straddle_progress_pct'), '%')} progress; "
            f"stage {out.get('straddle_stage','UNKNOWN')}"
        ),
        "opportunity": setup,
        "decision_color": "red" if direction == "BEARISH" else "green" if direction == "BULLISH" else "amber",
    })
    return out


def merge_evidence(base_path, trading_date: str):
    from multi_source_adapter import discover_sources, load_and_merge

    # Discover supporting families from the selected folder, but force the
    # BASE family to the exact snapshot currently being processed.
    bundle = discover_sources(base_path.parent, trading_date)
    bundle.files["BASE"] = base_path
    bundle = load_and_merge(bundle)

    if bundle.rows is None or bundle.rows.empty:
        raise ValueError(f"No merged source data found for selected snapshot: {base_path}")

    merged = bundle.rows.copy()
    merged["_source_BASE"] = True

    # Ensure only symbols present in the selected BASE snapshot are returned.
    base_symbols = set(
        merged["symbol"].astype(str).str.upper()
    ) if "symbol" in merged.columns else set()

    if base_symbols and "symbol" in merged.columns:
        merged = merged[merged["symbol"].astype(str).str.upper().isin(base_symbols)].copy()

    return merged, {"bundle": bundle, "base_path": base_path}
