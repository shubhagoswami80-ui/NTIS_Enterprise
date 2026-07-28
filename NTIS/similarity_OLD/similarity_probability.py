"""
=========================================================
NTIS Historical Similarity Engine
Module      : similarity_probability.py
Version     : 1.0.0
Release     : R1
Status      : Production Foundation

Calculates historical success probability from the
top ranked historical matches.
=========================================================
"""

from __future__ import annotations

import pandas as pd


class SimilarityProbability:
    """Estimate win probability from ranked historical matches."""

    def __init__(self, outcome_column: str = "Outcome"):
        self.outcome_column = outcome_column

    def calculate(self, ranked_df: pd.DataFrame) -> dict:
        if ranked_df.empty:
            return {
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "win_probability": 0.0,
                "confidence": "LOW",
            }

        if self.outcome_column not in ranked_df.columns:
            raise ValueError(f"Missing required column: {self.outcome_column}")

        outcomes = ranked_df[self.outcome_column].astype(str).str.upper()

        wins = outcomes.isin(["WIN", "SUCCESS", "TARGET"]).sum()
        losses = outcomes.isin(["LOSS", "FAIL", "STOPLOSS"]).sum()
        total = len(ranked_df)

        probability = round((wins / total) * 100.0, 2) if total else 0.0

        if probability >= 80:
            confidence = "VERY HIGH"
        elif probability >= 65:
            confidence = "HIGH"
        elif probability >= 50:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return {
            "matches": total,
            "wins": int(wins),
            "losses": int(losses),
            "win_probability": probability,
            "confidence": confidence,
        }
