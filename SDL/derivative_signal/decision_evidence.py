from __future__ import annotations

from typing import Any

import pandas as pd


SOURCE_LABELS = {
    "BASE": "Price/OI",
    "FUTURES": "Futures",
    "IV": "IV",
    "SUPPORT": "Support",
    "RESISTANCE": "Resistance",
    "VOLUME": "Volume",
}


def _num(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _source_present(row: dict[str, Any], role: str) -> bool:
    value = row.get(f"_source_{role}")
    return bool(value is True or str(value).strip().lower() in {"true", "1", "yes"})


def _directional_evidence(direction: str, signal: dict[str, Any]) -> tuple[list[str], list[str]]:
    confirmations: list[str] = []
    conflicts: list[str] = []

    options_dir = str(signal.get("options_direction", "NEUTRAL")).upper()
    futures_dir = str(signal.get("futures_direction", "NEUTRAL")).upper()
    volume = _num(signal.get("volume_change_pct"))
    oi = _num(signal.get("oi_change_pct"))
    pcr = _num(signal.get("pcr_change_pct"))
    progress = _num(signal.get("straddle_progress_pct"))

    if direction == "BULLISH":
        if options_dir == "BULLISH": confirmations.append("OPTIONS SUPPORT")
        elif options_dir == "BEARISH": conflicts.append("OPTIONS CONFLICT")
        if futures_dir == "BULLISH": confirmations.append("FUTURES SUPPORT")
        elif futures_dir == "BEARISH": conflicts.append("FUTURES CONFLICT")
        if volume is not None and volume > 0: confirmations.append("VOLUME SUPPORT")
        if oi is not None and oi > 0: confirmations.append("OI BUILDUP")
        if pcr is not None and pcr > 0: confirmations.append("PCR SUPPORT")
        if progress is not None and progress >= 75: confirmations.append("STRADDLE ACTIVE")
    elif direction == "BEARISH":
        if options_dir == "BEARISH": confirmations.append("OPTIONS SUPPORT")
        elif options_dir == "BULLISH": conflicts.append("OPTIONS CONFLICT")
        if futures_dir == "BEARISH": confirmations.append("FUTURES SUPPORT")
        elif futures_dir == "BULLISH": conflicts.append("FUTURES CONFLICT")
        if volume is not None and volume > 0: confirmations.append("VOLUME SUPPORT")
        if oi is not None and oi > 0: confirmations.append("OI BUILDUP")
        if pcr is not None and pcr < 0: confirmations.append("PCR SUPPORT")
        if progress is not None and progress >= 75: confirmations.append("STRADDLE ACTIVE")

    return confirmations, conflicts


def enrich_decision(signal: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = dict(signal)
    direction = str(out.get("direction", "NEUTRAL")).upper()
    price = _num(out.get("reference_price"))
    support = _num(out.get("support"))
    resistance = _num(out.get("resistance"))

    confirmations, conflicts = _directional_evidence(direction, out)

    room_value = None
    room_pct = None
    room_label = "LEVEL UNKNOWN"
    if price is not None and direction == "BULLISH" and resistance is not None:
        room_value = resistance - price
    elif price is not None and direction == "BEARISH" and support is not None:
        room_value = price - support

    if room_value is not None and price:
        room_pct = room_value / price * 100.0
        if room_value <= 0: room_label = "NO ROOM"
        elif room_pct <= 0.75: room_label = "LIMITED ROOM"
        elif room_pct <= 2.0: room_label = "ADEQUATE ROOM"
        else: room_label = "GOOD ROOM"

    location = str(out.get("location", "NOT_AVAILABLE"))
    if direction == "BULLISH":
        if location == "RESISTANCE_CROSSED": confirmations.append("RESISTANCE CROSSED")
        elif location == "AT_RESISTANCE": conflicts.append("AT RESISTANCE")
    elif direction == "BEARISH":
        if location == "SUPPORT_BROKEN": confirmations.append("SUPPORT BROKEN")
        elif location == "AT_SUPPORT": conflicts.append("AT SUPPORT")

    base_strength = int(out.get("strength") or 0)
    confluence = max(0, min(5, base_strength + min(2, len(confirmations)) - min(2, len(conflicts))))
    if direction == "NEUTRAL": confluence = 0

    source_roles = ["BASE"] if out.get("symbol") else []
    for role in SOURCE_LABELS:
        if role != "BASE" and _source_present(row, role):
            source_roles.append(role)

    missing_roles = [r for r in ("FUTURES", "IV", "SUPPORT", "RESISTANCE", "VOLUME") if r not in source_roles]
    usable_non_base = len(source_roles) - 1

    if usable_non_base >= 4 and room_label not in {"LEVEL UNKNOWN", "NO ROOM"} and not conflicts:
        quality = "HIGH"
    elif usable_non_base >= 2 and room_label != "NO ROOM" and len(conflicts) <= 1:
        quality = "MEDIUM"
    else:
        quality = "LOW"

    if direction == "NEUTRAL":
        action, opportunity = "WATCH", "NO DIRECTION"
    elif len(conflicts) >= 2:
        action, opportunity = "WAIT", "CONFLICT"
    elif room_label == "NO ROOM":
        action, opportunity = "AVOID", "NO ROOM"
    elif room_label == "LEVEL UNKNOWN":
        action, opportunity = "WAIT", "LEVEL REQUIRED"
    elif confluence >= 4 and quality == "HIGH":
        action, opportunity = "ENTER / CONTINUE", "HIGH CONFLUENCE"
    elif confluence >= 3:
        action, opportunity = "CONTINUE / CONFIRM", "DEVELOPING"
    else:
        action, opportunity = "WAIT", "PARTIAL EVIDENCE"

    out.update({
        "confirmations_detail": confirmations,
        "conflicts_detail": conflicts,
        "room_value": room_value,
        "room_pct": room_pct,
        "room_label": room_label,
        "source_roles": source_roles,
        "missing_source_roles": missing_roles,
        "source_family_count": len(source_roles),
        "evidence_summary": f"{len(source_roles)}/6 source families available" + (
            f" • missing: {', '.join(missing_roles)}" if missing_roles else " • complete"
        ),
        "confluence_score": confluence,
        "confluence_label": "HIGH" if confluence >= 4 else "MEDIUM" if confluence >= 3 else "LOW",
        "decision_quality": quality,
        "action": action,
        "opportunity": opportunity,
        "decision_color": "red" if direction == "BEARISH" else "green" if direction == "BULLISH" else "amber",
        "momentum_state": (
            "ACCELERATING" if len(confirmations) >= 3 and not conflicts
            else "WEAKENING" if conflicts
            else "SUSTAINING" if direction != "NEUTRAL"
            else "NEUTRAL"
        ),
    })
    return out


def merge_evidence(base_path, trading_date: str):
    from multi_source_adapter import discover_sources, load_and_merge

    bundle = load_and_merge(discover_sources(base_path.parent, trading_date))
    if bundle.rows is None or bundle.rows.empty:
        raise ValueError(f"No merged source data found. Selected folder: {base_path.parent}")

    merged = bundle.rows.copy()
    try:
        from multi_source_adapter import _clean, _read
        base_df = _clean(_read(base_path, "BASE"))
        if not base_df.empty and "symbol" in base_df.columns:
            symbols = set(base_df["symbol"].astype(str).str.upper())
            merged = merged[merged["symbol"].astype(str).str.upper().isin(symbols)].copy()
    except Exception:
        pass

    merged["_source_BASE"] = True
    return merged, {"bundle": bundle, "base_path": base_path}
