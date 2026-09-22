from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Iterable
import json, math
from pathlib import Path

DEFAULT_REQUIRED = [
    "Symbol", "Close", "ATM Straddle Price", "ATM Straddle %",
    "OI Chg", "OI Chg %", "Volume", "IV", "PCR Chg"
]

@dataclass(frozen=True)
class UniverseDecision:
    symbol: str
    eligible: bool
    priority_score: float
    reasons: tuple[str, ...]
    evaluated_at: str
    filter_version: str

def _num(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)): return None
        s=str(v).strip().replace(",", "")
        if not s: return None
        x=float(s)
        return x if math.isfinite(x) else None
    except Exception:
        return None

def load_config(path: str | Path) -> dict:
    p=Path(path)
    if not p.exists():
        return {
            "version":"W73_UNIVERSE_V1",
            "required_fields":DEFAULT_REQUIRED,
            "exclude_symbols":[],
            "min_volume":None,
            "min_abs_oi_chg":None,
            "min_abs_straddle_pct":None,
            "max_symbols":50
        }
    return json.loads(p.read_text(encoding="utf-8"))

def _activity_score(r: dict) -> float:
    # Priority only; it does not decide eligibility.
    vals=[]
    for k in ("Volume Chg (%)","OI Chg %","ATM Straddle %","Price Chg %","IV Chg %"):
        x=_num(r.get(k))
        if x is not None: vals.append(abs(x))
    return round(sum(vals)/len(vals), 6) if vals else 0.0

def evaluate(rows: Iterable[dict], evaluated_at: str, config: dict) -> list[UniverseDecision]:
    required=config.get("required_fields", DEFAULT_REQUIRED)
    excluded={str(x).strip().upper() for x in config.get("exclude_symbols", [])}
    min_volume=config.get("min_volume")
    min_oi=config.get("min_abs_oi_chg")
    min_straddle=config.get("min_abs_straddle_pct")
    version=str(config.get("version","W73_UNIVERSE_V1"))
    decisions=[]
    for r in rows:
        sym=str(r.get("Symbol","")).strip().upper()
        if not sym: continue
        reasons=[]
        if sym in excluded: reasons.append("EXCLUDED_SYMBOL")
        missing=[f for f in required if r.get(f) in (None,"","NA","N/A")]
        if missing: reasons.append("MISSING_REQUIRED:"+",".join(missing))
        vol=_num(r.get("Volume"))
        oi=_num(r.get("OI Chg"))
        sp=_num(r.get("ATM Straddle %"))
        if min_volume is not None and (vol is None or vol < float(min_volume)): reasons.append("VOLUME_BELOW_MIN")
        if min_oi is not None and (oi is None or abs(oi) < float(min_oi)): reasons.append("OI_BELOW_MIN")
        if min_straddle is not None and (sp is None or abs(sp) < float(min_straddle)): reasons.append("STRADDLE_MOVE_BELOW_MIN")
        eligible=not reasons
        decisions.append(UniverseDecision(sym, eligible, _activity_score(r) if eligible else 0.0,
                                          tuple(reasons), evaluated_at, version))
    eligible=sorted([d for d in decisions if d.eligible], key=lambda x:(-x.priority_score,x.symbol))
    cap=config.get("max_symbols")
    if cap:
        top=set(x.symbol for x in eligible[:int(cap)])
        decisions=[d if not d.eligible or d.symbol in top else UniverseDecision(
            d.symbol,False,d.priority_score,("PRIORITY_CAP",),d.evaluated_at,d.filter_version
        ) for d in decisions]
    return decisions
