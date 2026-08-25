from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


# Frozen SDL decision gates.
PRIMARY_PRICE_MOVE_PCT = 0.75
EARLY_STRADDLE_PROGRESS_PCT = 25.0
MID_STRADDLE_PROGRESS_PCT = 50.0
APPROACH_STRADDLE_PROGRESS_PCT = 75.0
BREAKOUT_STRADDLE_PROGRESS_PCT = 100.0


@dataclass(frozen=True)
class Factor:
    name: str
    label: str
    weight: float
    state: str  # SUPPORT, CONTRADICT, NEUTRAL, UNAVAILABLE


def _num(value):
    try:
        return pd.to_numeric(value, errors="coerce")
    except Exception:
        return np.nan


def _norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    if "Symbol" in out.columns:
        out["Symbol"] = out["Symbol"].astype(str).str.strip().str.upper()
    return out


def _find_alias(df: pd.DataFrame, patterns: Iterable[str]) -> str | None:
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for key, original in lowered.items():
        compact = key.replace("_", " ").replace("-", " ")
        if all(token in compact for token in patterns):
            return original
    return None


def _future_oi_column(df: pd.DataFrame) -> str | None:
    aliases = [
        ("futures", "oi", "chg"),
        ("future", "oi", "chg"),
        ("futures", "oi", "change"),
        ("future", "oi", "change"),
        ("fut", "oi", "chg"),
    ]
    for pattern in aliases:
        col = _find_alias(df, pattern)
        if col:
            return col
    return "OI Chg %" if "OI Chg %" in df.columns else None


def _stage(progress: float) -> str:
    # Progress is calculated from the frozen opening straddle premium:
    # abs(CMP - O) / S * 100.
    # These are non-overlapping decision bands.
    if progress >= BREAKOUT_STRADDLE_PROGRESS_PCT:
        return "100%+ BREAKOUT"
    if progress >= APPROACH_STRADDLE_PROGRESS_PCT:
        return "75–<100% APPROACHING"
    if progress >= MID_STRADDLE_PROGRESS_PCT:
        return "50–<75%"
    return "25–<50% EARLY"


def _strength_label(strength: float, contradict_weight: float, available_weight: float) -> str:
    if available_weight <= 0:
        return "WAIT"
    contradiction_ratio = contradict_weight / available_weight
    if contradiction_ratio >= 0.40:
        return "WAIT / CONFLICT"
    if strength >= 80:
        return "STRONG"
    if strength >= 65:
        return "SUPPORTED"
    if strength >= 50:
        return "DEVELOPING"
    return "WAIT"


def evaluate_row(row: pd.Series, orb_status: str = "ORB N/A") -> dict:
    opening = _num(row.get("_frozen_open"))
    current = _num(row.get("_current_price"))
    premium = _num(row.get("_frozen_premium"))

    if not np.isfinite(opening) or not np.isfinite(current) or not np.isfinite(premium) or premium <= 0:
        return {"eligible": False, "reason": "missing frozen opening base"}

    move = current - opening
    direction = "UP" if move > 0 else "DOWN" if move < 0 else ""
    abs_price_move_pct = abs(move) / opening * 100.0 if opening else np.nan
    progress = abs(move) / premium * 100.0

    # Primary gate: the underlying must first move at least +/-0.75%.
    if not direction or not np.isfinite(abs_price_move_pct) or abs_price_move_pct < PRIMARY_PRICE_MOVE_PCT:
        return {"eligible": False, "reason": "below ±0.75% primary price gate"}

    # Straddle progress is the second gate for entering the Decision Center.
    # It is measured from the frozen opening straddle premium:
    #   abs(CMP - O) / S * 100
    # Therefore 25/50/75/100 are fractions of THIS stock's frozen S,
    # never percentages of CMP and never percentages of ATM Straddle %.
    if progress < EARLY_STRADDLE_PROGRESS_PCT:
        return {"eligible": False, "reason": "below 25% straddle progress"}

    price_change = _num(row.get("Price Chg %"))
    price_aligned = True if not np.isfinite(price_change) else (
        (direction == "UP" and price_change > 0) or
        (direction == "DOWN" and price_change < 0)
    )

    factors: list[Factor] = [
        Factor("price", "PRICE DIRECTION", 25, "SUPPORT" if price_aligned else "CONTRADICT"),
    ]

    fut = _num(row.get("_futures_oi"))
    if np.isfinite(fut):
        state = "SUPPORT" if abs(fut) >= 0.25 else "NEUTRAL"
        factors.append(Factor("futures_oi", "FUTURES OI", 15, state))

    ce = _num(row.get("Tot CE OI Chg %"))
    pe = _num(row.get("Tot PE OI Chg %"))
    if np.isfinite(ce) or np.isfinite(pe):
        support = (
            (direction == "UP" and ((np.isfinite(ce) and ce <= -0.25) or (np.isfinite(pe) and pe >= 0.25))) or
            (direction == "DOWN" and ((np.isfinite(ce) and ce >= 0.25) or (np.isfinite(pe) and pe <= -0.25)))
        )
        contradict = (
            (direction == "UP" and np.isfinite(ce) and np.isfinite(pe) and ce >= 0.25 and pe <= -0.25) or
            (direction == "DOWN" and np.isfinite(ce) and np.isfinite(pe) and ce <= -0.25 and pe >= 0.25)
        )
        state = "CONTRADICT" if contradict else "SUPPORT" if support else "NEUTRAL"
        factors.append(Factor("options_oi", "CE/PE OI", 20, state))

    pcr = _num(row.get("PCR Chg %"))
    if np.isfinite(pcr):
        if direction == "UP":
            state = "SUPPORT" if pcr >= 0.05 else "CONTRADICT" if pcr <= -0.05 else "NEUTRAL"
        else:
            state = "SUPPORT" if pcr <= -0.05 else "CONTRADICT" if pcr >= 0.05 else "NEUTRAL"
        factors.append(Factor("pcr", "PCR", 10, state))

    iv = _num(row.get("IV Chg %"))
    if np.isfinite(iv):
        state = "SUPPORT" if iv >= 0.50 else "CONTRADICT" if iv <= -0.50 else "NEUTRAL"
        factors.append(Factor("iv", "IV", 10, state))

    pe_ce = _num(row.get("Tot PE-CE OI Chg"))
    if np.isfinite(pe_ce):
        if direction == "UP":
            state = "SUPPORT" if pe_ce > 10 else "CONTRADICT" if pe_ce < -10 else "NEUTRAL"
        else:
            state = "SUPPORT" if pe_ce < -10 else "CONTRADICT" if pe_ce > 10 else "NEUTRAL"
        factors.append(Factor("pe_ce", "PE−CE OI", 10, state))

    if orb_status not in {"ORB N/A", "ORB PARTIAL"}:
        if (direction == "UP" and orb_status == "ORB ↑") or (direction == "DOWN" and orb_status == "ORB ↓"):
            state = "SUPPORT"
        elif orb_status in {"ORB ↑", "ORB ↓"}:
            state = "CONTRADICT"
        else:
            state = "NEUTRAL"
        factors.append(Factor("orb", "15-MIN ORB", 10, state))

    secondary = [f for f in factors if f.name != "price"]
    available_weight = sum(f.weight for f in secondary)
    support_weight = sum(f.weight for f in secondary if f.state == "SUPPORT")
    contradict_weight = sum(f.weight for f in secondary if f.state == "CONTRADICT")

    # Preserve the existing factor weights; use them to prioritize rather than
    # turning a single secondary score into the primary selector.
    strength = 25.0 if price_aligned else 10.0
    if available_weight:
        strength += 75.0 * (support_weight / available_weight)
        strength -= 15.0 * (contradict_weight / available_weight)
    strength = float(np.clip(strength, 0, 100))

    stage = _stage(progress)
    strength_label = _strength_label(strength, contradict_weight, available_weight)

    if direction == "UP":
        direction_label = "BULLISH"
    else:
        direction_label = "BEARISH"

    if strength_label == "WAIT / CONFLICT":
        decision = f"{direction_label} · {stage} · WAIT / CONFLICT"
    else:
        decision = f"{direction_label} · {stage} · {strength_label}"

    factual_breakout = (
        (direction == "UP" and current > opening + premium) or
        (direction == "DOWN" and current < opening - premium)
    )

    return {
        "eligible": True,
        "symbol": str(row.get("Symbol", "")).strip().upper(),
        "direction": direction,
        "direction_label": direction_label,
        "price_move_pct": round(abs_price_move_pct, 2),
        "signed_price_move_pct": round(move / opening * 100.0, 2),
        "progress": round(progress, 1),
        "stage": stage,
        "progress_band": stage,
        "factual_breakout": bool(factual_breakout),
        "upper_breakout": opening + premium,
        "lower_breakout": opening - premium,
        "strength": round(strength, 1),
        "strength_label": strength_label,
        "factors": factors,
        "support_weight": support_weight,
        "contradict_weight": contradict_weight,
        "available_weight": available_weight,
        "orb": orb_status,
        "price_change": price_change,
        "decision": decision,
    }


def build_current_predictions(
    source: pd.DataFrame,
    frozen_base: dict,
    orb_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    if source is None or source.empty or not frozen_base:
        return pd.DataFrame()

    source = _norm_columns(source)
    future_col = _future_oi_column(source)
    records = []

    for _, row in source.iterrows():
        symbol = str(row.get("Symbol", "")).strip().upper()
        if not symbol or symbol not in frozen_base:
            continue

        base = frozen_base.get(symbol) or {}
        enriched = row.copy()
        enriched["_frozen_open"] = base.get("open_price")
        enriched["_frozen_premium"] = base.get("opening_straddle_premium")

        # SDL pipeline currently defines Close as the configured current/replay
        # price field. Do not substitute a later value.
        enriched["_current_price"] = row.get("Close", row.get("Current Price", row.get("CMP")))

        if future_col:
            enriched["_futures_oi"] = row.get(future_col)

        result = evaluate_row(enriched, (orb_map or {}).get(symbol, "ORB N/A"))
        if result.get("eligible"):
            result["symbol"] = symbol
            result["opening_price"] = base.get("open_price")
            result["frozen_straddle"] = base.get("opening_straddle_premium")
            result["current_price"] = enriched["_current_price"]
            records.append(result)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).sort_values(
        ["factual_breakout", "strength", "progress", "symbol"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def factor_labels(result: dict) -> list[str]:
    labels = []
    for f in result.get("factors", []):
        if f.state == "SUPPORT":
            labels.append(f"✓ {f.label}")
        elif f.state == "CONTRADICT":
            labels.append(f"✕ {f.label}")
        elif f.state == "NEUTRAL":
            labels.append(f"• {f.label}")
    return labels
