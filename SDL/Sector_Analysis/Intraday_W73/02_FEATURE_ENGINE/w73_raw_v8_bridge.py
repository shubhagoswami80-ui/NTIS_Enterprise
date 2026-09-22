from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
import csv


V8_COLUMNS = (
    "orb_minutes","maturity","orb_dir","price_dir","fut_dir","option_dir",
    "fut_state","volume_state","ce_state","pe_state","pec_state",
    "fut_oi_state","ce_pct_state","pe_pct_state","pec_pct_state",
    "fut_pct_state","price_state","orb_agree","evidence_agreement",
    "persistent","strength_bucket","core_count_band","magnitude_count_band",
    "orb_fut_agree","orb_price_agree",
)

RAW_NUMERIC = (
    "Open","High","Low","Close","VWAP","Price Chg","Price Chg %",
    "IV","IV Chg","IV Chg %","OI Chg","OI Chg %","Volume",
    "Volume Chg (%)","PCR Chg","PCR Chg %","Tot CE OI","Tot PE OI",
    "Tot PE-CE OI","Tot CE OI Chg","Tot CE OI Chg %","Tot PE OI Chg",
    "Tot PE OI Chg %","IVR","IVP","ATM Straddle Price","ATM Straddle %",
)

@dataclass(frozen=True)
class V8Context:
    trading_date: str
    observation_time: datetime
    orb_minutes: int
    maturity: str

@dataclass(frozen=True)
class BridgeResult:
    status: str
    values: dict[str, Any]
    warnings: tuple[str, ...] = ()

def _num(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _sign(v: float | None) -> str | None:
    if v is None:
        return None
    if v > 0:
        return "POSITIVE"
    if v < 0:
        return "NEGATIVE"
    return "FLAT"

def _direction(price: float | None, oi: float | None) -> str | None:
    # Directional family only; no fabricated value when either component is absent.
    if price is None or oi is None:
        return None
    if price > 0 and oi > 0: return "LONG"
    if price < 0 and oi > 0: return "SHORT"
    if price > 0 and oi < 0: return "SHORT_COVER"
    if price < 0 and oi < 0: return "LONG_UNWIND"
    return "NEUTRAL"

def load_matrix_vocab(matrix_path: Path) -> dict[str, set[str]]:
    """Read allowed vocabulary from the authoritative local V8 matrix."""
    if not matrix_path.exists():
        raise FileNotFoundError(matrix_path)
    with matrix_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        vocab = {c: set() for c in V8_COLUMNS if c in (reader.fieldnames or [])}
        for row in reader:
            for c in vocab:
                value = row.get(c)
                if value not in (None, ""):
                    vocab[c].add(str(value))
    return vocab

def derive_raw_features(row: Mapping[str, Any], ctx: V8Context) -> BridgeResult:
    """Conservative raw-to-state bridge.

    This is intentionally fail-closed. It derives only elementary states from
    explicit source fields. It does NOT claim parity with historical V8 semantics
    until the parity validator passes against the authoritative matrix/research.
    """
    warnings: list[str] = []
    price_pct = _num(row, "Price Chg %")
    oi_pct = _num(row, "OI Chg %")
    ce_pct = _num(row, "Tot CE OI Chg %")
    pe_pct = _num(row, "Tot PE OI Chg %")
    pec_pct = _num(row, "PCR Chg %")
    fut_price = price_pct
    volume = _num(row, "Volume Chg (%)")

    values = {
        "orb_minutes": ctx.orb_minutes,
        "maturity": ctx.maturity,
        "orb_dir": None,
        "price_dir": _sign(price_pct),
        "fut_dir": _direction(fut_price, oi_pct),
        "option_dir": None,
        "fut_state": _direction(fut_price, oi_pct),
        "volume_state": _sign(volume),
        "ce_state": _sign(ce_pct),
        "pe_state": _sign(pe_pct),
        "pec_state": _sign(pec_pct),
        "fut_oi_state": _sign(oi_pct),
        "ce_pct_state": _sign(ce_pct),
        "pe_pct_state": _sign(pe_pct),
        "pec_pct_state": _sign(pec_pct),
        "fut_pct_state": _sign(oi_pct),
        "price_state": _sign(price_pct),
        "orb_agree": None,
        "evidence_agreement": None,
        "persistent": None,
        "strength_bucket": None,
        "core_count_band": None,
        "magnitude_count_band": None,
        "orb_fut_agree": None,
        "orb_price_agree": None,
    }

    if any(v is None for v in values.values()):
        warnings.append("INCOMPLETE_V8_VECTOR")
    return BridgeResult("DERIVED_PROVISIONAL", values, tuple(warnings))

def validate_vector(values: Mapping[str, Any]) -> list[str]:
    missing = [c for c in V8_COLUMNS if values.get(c) is None]
    return missing
