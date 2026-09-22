from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass
class StrategyBaseline:
    candidate_id: str
    holdout_rate: float
    holdout_n: int
    holdout_dates: int
    holdout_symbols: int
    conditions: dict

class W73Strategy:
    """Frozen maximum robust V12.6 candidate, reconstructed locally."""

    def __init__(self, store):
        self.store = store

    def baseline(self):
        df = self.store.validation()
        required = {"holdout_rate","holdout_n","holdout_dates","holdout_symbols"}
        if df.empty or not required.issubset(df.columns):
            return None
        r = df.copy()
        for c in required:
            r[c] = pd.to_numeric(r[c], errors="coerce")
        r = r.dropna(subset=list(required))
        r = r[(r.holdout_n >= 30) & (r.holdout_dates >= 3) &
              (r.holdout_symbols >= 10)]
        if r.empty:
            return None
        row = r.loc[r.holdout_rate.idxmax()]
        meta = {"candidate_id","pattern_id","rank","score","holdout_rate",
                "holdout_n","holdout_dates","holdout_symbols",
                "train_rate","train_n","train_dates","train_symbols"}
        conditions = {}
        for c in r.columns:
            if c in meta:
                continue
            v = row[c]
            if pd.notna(v):
                conditions[c] = v.item() if hasattr(v, "item") else v
        return StrategyBaseline(
            str(row.get("candidate_id", row.get("pattern_id", "MAX_ROBUST"))),
            float(row.holdout_rate), int(row.holdout_n),
            int(row.holdout_dates), int(row.holdout_symbols), conditions)

    def match_live(self, live, baseline):
        if live.empty or baseline is None:
            return pd.DataFrame()
        comparable = [c for c in baseline.conditions
                      if c in live.columns
                      and c not in {"symbol","trade_date","timestamp","reached_0_5x"}]
        if not comparable:
            return pd.DataFrame()
        out = live.copy()
        out["_w73_match_count"] = 0
        out["_w73_compared"] = len(comparable)
        for c in comparable:
            expected = baseline.conditions[c]
            valid = out[c].notna()
            out["_w73_match_count"] += (
                valid & (out[c].astype(str).str.strip().str.upper()
                         == str(expected).strip().upper())
            ).astype(int)
        out["_w73_match_pct"] = out["_w73_match_count"] / out["_w73_compared"] * 100
        out["_w73_exact_match"] = out["_w73_match_count"] == out["_w73_compared"]
        return out.sort_values(["_w73_exact_match","_w73_match_pct"],
                               ascending=[False,False])
