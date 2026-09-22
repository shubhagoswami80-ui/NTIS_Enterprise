from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import pandas as pd

@dataclass(frozen=True)
class W73Variant:
    name: str
    candidate_id: str
    holdout_rate: float
    holdout_n: int
    holdout_dates: int
    holdout_symbols: int
    conditions: dict[str, Any]

    def matches(self, row: pd.Series) -> bool:
        for feature, expected in self.conditions.items():
            if feature not in row.index or pd.isna(row[feature]):
                return False
            if str(row[feature]).strip().upper() != str(expected).strip().upper():
                return False
        return True

class W73StrategyV1:
    """Two explicitly preserved candidates tied at the 72.093% maximum."""

    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parent
        self.baseline_file = self.root / "00_BASELINE" / "strategy_baseline_v1_tied_max.json"
        self.variants = self._load_variants()

    def _load_variants(self):
        if not self.baseline_file.exists():
            raise FileNotFoundError(self.baseline_file)
        p = json.loads(self.baseline_file.read_text(encoding="utf-8"))
        candidates = p.get("candidates", [])
        if len(candidates) != 2:
            raise RuntimeError(f"Expected exactly 2 tied candidates; found {len(candidates)}")
        return [
            W73Variant(
                name=f"W73-{'A' if i == 0 else 'B'}",
                candidate_id=str(x["candidate_id"]),
                holdout_rate=float(x["holdout_rate"]),
                holdout_n=int(x["holdout_n"]),
                holdout_dates=int(x["holdout_dates"]),
                holdout_symbols=int(x["holdout_symbols"]),
                conditions=dict(x["conditions"]),
            )
            for i, x in enumerate(candidates)
        ]

    def classify(self, row: pd.Series):
        matches = [v.name for v in self.variants if v.matches(row)]
        return matches[0] if len(matches) == 1 else None

    def classify_frame(self, df: pd.DataFrame):
        out = df.copy()
        out["w73_variant"] = out.apply(self.classify, axis=1)
        out["w73_qualified"] = out["w73_variant"].notna()
        return out
