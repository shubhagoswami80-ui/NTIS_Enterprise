from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


EARLY_THRESHOLD = 22.0
TRADEABLE_THRESHOLD = 70.0
MIN_SECONDARY_WEIGHT = 40.0


@dataclass(frozen=True)
class Factor:
    name: str
    label: str
    weight: float
    state: str  # SUPPORT, CONTRADICT, NEUTRAL, UNAVAILABLE


def _num(value):
    try:
        value = pd.to_numeric(value, errors="coerce")
    except Exception:
        return np.nan
    return value


def _series_num(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    if "Symbol" in out.columns:
        out["Symbol"] = out["Symbol"].astype(str).str.strip().str.upper()
    return out


def coalesce_source_sheets(path) -> pd.DataFrame:
    """Read every source sheet and coalesce the richest available values by Symbol."""
    if path is None:
        return pd.DataFrame()
    try:
        sheets = pd.read_excel(path, sheet_name=None)
    except Exception:
        return pd.DataFrame()

    frames = []
    for sheet_name, raw in sheets.items():
        if raw is None or raw.empty or "Symbol" not in raw.columns:
            continue
        x = _norm_columns(raw)
        x["_sheet"] = str(sheet_name)
        frames.append(x)

    if not frames:
        return pd.DataFrame()

    all_rows = pd.concat(frames, ignore_index=True, sort=False)
    all_rows = all_rows.drop_duplicates("Symbol", keep="last")
    return all_rows.reset_index(drop=True)


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

    # In the current Daywise contract, OI Chg % is the available futures-OI
    # participation field when no separately named futures-OI column exists.
    return "OI Chg %" if "OI Chg %" in df.columns else None


def _explicit_orb_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    hi = None
    lo = None
    for c in df.columns:
        k = str(c).strip().lower().replace("_", " ")
        if hi is None and ("orb" in k or "opening range" in k) and "high" in k:
            hi = c
        if lo is None and ("orb" in k or "opening range" in k) and "low" in k:
            lo = c
    return hi, lo


def evaluate_row(row: pd.Series, orb_status: str = "ORB N/A") -> dict:
    opening = _num(row.get("_frozen_open"))
    current = _num(row.get("_current_price"))
    premium = _num(row.get("_frozen_premium"))

    if not np.isfinite(opening) or not np.isfinite(current) or not np.isfinite(premium) or premium <= 0:
        return {"eligible": False, "reason": "missing frozen opening base"}

    move = current - opening
    direction = "UP" if move > 0 else "DOWN" if move < 0 else ""
    progress = abs(move) / premium * 100.0

    if not direction or progress <= EARLY_THRESHOLD:
        return {"eligible": False, "reason": "below early-entry threshold"}

    price_change = _num(row.get("Price Chg %"))
    if np.isfinite(price_change):
        price_aligned = (direction == "UP" and price_change > 0) or (direction == "DOWN" and price_change < 0)
    else:
        price_aligned = True

    if not price_aligned:
        return {"eligible": False, "reason": "price direction contradiction"}

    factors: list[Factor] = [
        Factor("price", "PRICE ALIGNED", 25, "SUPPORT"),
    ]

    fut = _num(row.get("_futures_oi"))
    if np.isfinite(fut):
        state = "SUPPORT" if abs(fut) >= 0.25 else "NEUTRAL"
        factors.append(Factor("futures_oi", "FUTURES OI PARTICIPATION", 15, state))

    ce = _num(row.get("Tot CE OI Chg %"))
    pe = _num(row.get("Tot PE OI Chg %"))
    if np.isfinite(ce) or np.isfinite(pe):
        support = ((direction == "UP") and ((np.isfinite(ce) and ce <= -0.25) or (np.isfinite(pe) and pe >= 0.25))) or \
                  ((direction == "DOWN") and ((np.isfinite(ce) and ce >= 0.25) or (np.isfinite(pe) and pe <= -0.25)))
        contradict = ((direction == "UP") and np.isfinite(ce) and np.isfinite(pe) and ce >= 0.25 and pe <= -0.25) or \
                     ((direction == "DOWN") and np.isfinite(ce) and np.isfinite(pe) and ce <= -0.25 and pe >= 0.25)
        state = "CONTRADICT" if contradict else "SUPPORT" if support else "NEUTRAL"
        factors.append(Factor("options_oi", "CE/PE OI STRUCTURE", 20, state))

    pcr = _num(row.get("PCR Chg %"))
    if np.isfinite(pcr):
        if direction == "UP":
            state = "SUPPORT" if pcr >= 0.05 else "CONTRADICT" if pcr <= -0.05 else "NEUTRAL"
        else:
            state = "SUPPORT" if pcr <= -0.05 else "CONTRADICT" if pcr >= 0.05 else "NEUTRAL"
        factors.append(Factor("pcr", "PCR DIRECTION", 10, state))

    iv = _num(row.get("IV Chg %"))
    if np.isfinite(iv):
        state = "SUPPORT" if iv >= 0.50 else "CONTRADICT" if iv <= -0.50 else "NEUTRAL"
        factors.append(Factor("iv", "IV MOVEMENT", 10, state))

    pe_ce = _num(row.get("Tot PE-CE OI Chg"))
    if np.isfinite(pe_ce):
        if direction == "UP":
            state = "SUPPORT" if pe_ce > 10 else "CONTRADICT" if pe_ce < -10 else "NEUTRAL"
        else:
            state = "SUPPORT" if pe_ce < -10 else "CONTRADICT" if pe_ce > 10 else "NEUTRAL"
        factors.append(Factor("pe_ce", "PE-CE OI BALANCE", 10, state))

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
    strength = 25.0
    if available_weight:
        strength += 75.0 * (support_weight / available_weight)
        strength -= 15.0 * (contradict_weight / available_weight)
    strength = float(np.clip(strength, 0, 100))

    eligible = available_weight >= MIN_SECONDARY_WEIGHT
    tradeable = eligible and strength >= TRADEABLE_THRESHOLD and contradict_weight <= max(10.0, available_weight * 0.20)

    return {
        "eligible": True,
        "tradeable": tradeable,
        "symbol": str(row.get("Symbol", "")).strip().upper(),
        "direction": direction,
        "progress": round(progress, 1),
        "strength": round(strength, 1),
        "factors": factors,
        "support_weight": support_weight,
        "contradict_weight": contradict_weight,
        "available_weight": available_weight,
        "orb": orb_status,
        "price_change": price_change,
        "decision": "TRADEABLE" if tradeable else "NO TRADE",
    }


def build_current_predictions(source: pd.DataFrame, frozen_base: dict, orb_map: dict[str, str] | None = None) -> pd.DataFrame:
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
        enriched["_current_price"] = row.get("Close", row.get("Current Price", row.get("CMP")))

        if future_col:
            enriched["_futures_oi"] = row.get(future_col)

        result = evaluate_row(enriched, (orb_map or {}).get(symbol, "ORB N/A"))
        if result.get("eligible"):
            result["symbol"] = symbol
            records.append(result)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).sort_values(
        ["tradeable", "strength", "progress", "symbol"],
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
