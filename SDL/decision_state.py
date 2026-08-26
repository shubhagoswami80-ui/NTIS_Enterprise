from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import pandas as pd

from config import STATE_DIR


DECISION_STATE_FILE = Path(STATE_DIR) / "decision_state.json"


@dataclass
class StockDecisionState:
    symbol: str
    timestamp: str
    direction: str
    stage: str
    progress: float
    strength_label: str
    strength: float
    factual_breakout: bool
    decision: str
    previous_stage: str = ""
    previous_strength_label: str = ""
    transition: str = "NEW"


def _load() -> dict:
    if not DECISION_STATE_FILE.exists():
        return {"trading_dates": {}}
    try:
        return json.loads(DECISION_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"trading_dates": {}}


def _save(data: dict) -> None:
    DECISION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DECISION_STATE_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def clear_day(trading_date: str) -> None:
    data = _load()
    data.setdefault("trading_dates", {}).pop(str(trading_date), None)
    _save(data)


def apply_candidates(candidates: pd.DataFrame, timestamp: pd.Timestamp) -> pd.DataFrame:
    """Attach previous per-stock state for continuity; does not alter selection/scoring."""
    if candidates is None or candidates.empty:
        return pd.DataFrame() if candidates is None else candidates.copy()

    ts = pd.Timestamp(timestamp)
    trading_date = ts.date().isoformat()
    data = _load()
    day = data.setdefault("trading_dates", {}).setdefault(trading_date, {})
    out = candidates.copy()
    transitions = []
    previous_stage = []
    previous_strength = []

    for _, row in out.iterrows():
        symbol = str(row.get("symbol", "")).upper()
        prev = day.get(symbol, {})
        old_stage = str(prev.get("stage", ""))
        old_strength = str(prev.get("strength_label", ""))
        new_stage = str(row.get("stage", ""))
        new_strength = str(row.get("strength_label", ""))
        if not prev:
            transition = "NEW"
        elif old_stage != new_stage:
            transition = f"{old_stage} → {new_stage}"
        elif old_strength != new_strength:
            transition = f"{old_strength} → {new_strength}"
        else:
            transition = "UNCHANGED"
        previous_stage.append(old_stage or "—")
        previous_strength.append(old_strength or "—")
        transitions.append(transition)

        day[symbol] = {
            "timestamp": ts.isoformat(),
            "direction": str(row.get("direction", "")),
            "stage": new_stage,
            "progress": float(row.get("progress", 0) or 0),
            "strength_label": new_strength,
            "strength": float(row.get("strength", 0) or 0),
            "factual_breakout": bool(row.get("factual_breakout", False)),
            "decision": str(row.get("decision", "")),
        }

    out["PREVIOUS STAGE"] = previous_stage
    out["PREVIOUS CONFIRMATION"] = previous_strength
    out["STATE TRANSITION"] = transitions
    _save(data)
    return out
