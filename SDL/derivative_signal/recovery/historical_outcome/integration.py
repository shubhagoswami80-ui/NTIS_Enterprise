from __future__ import annotations

from typing import Any
import pandas as pd

from .engine import HistoricalOutcomeEngine, OutcomeConfig


def build_historical_outcome_evidence(
    unusual_events: pd.DataFrame,
    observations: pd.DataFrame,
    config: OutcomeConfig | None = None,
) -> dict[str, Any]:
    """Attach forward outcomes to upstream unusual PIT evidence.

    Upstream PIT rows remain unchanged; this function creates a separate
    evidence dataframe and explicitly marks the result as non-selection data.
    """
    engine = HistoricalOutcomeEngine(config)
    outcomes = engine.evaluate(unusual_events, observations)
    return {
        "events": unusual_events.copy(),
        "outcomes": outcomes,
        "summary": summarize_outcomes(outcomes),
        "is_selection_gate": False,
    }


def summarize_outcomes(outcomes: pd.DataFrame) -> dict[str, Any]:
    if outcomes is None or outcomes.empty:
        return {
            "rows": 0,
            "symbols": 0,
            "windows": [],
            "resolved_returns": 0,
            "positive": 0,
            "negative": 0,
            "flat": 0,
        }
    return {
        "rows": int(len(outcomes)),
        "symbols": int(outcomes["symbol"].nunique()),
        "windows": sorted(outcomes["outcome_window"].dropna().astype(str).unique().tolist()),
        "resolved_returns": int(outcomes["return_pct"].notna().sum()),
        "positive": int((outcomes["directional_outcome"] == "POSITIVE").sum()),
        "negative": int((outcomes["directional_outcome"] == "NEGATIVE").sum()),
        "flat": int((outcomes["directional_outcome"] == "FLAT").sum()),
    }
