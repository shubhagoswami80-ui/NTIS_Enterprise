"""
=========================================================
NTIS Historical Similarity Engine
Module      : similarity_calculator.py
Version     : 1.0.0
Release     : R1
Status      : Production Foundation

Public API
----------
SimilarityCalculator.calculate()
SimilarityCalculator.score_row()
=========================================================
"""

from __future__ import annotations

import logging
import pandas as pd


class SimilarityCalculator:
    """Calculates weighted similarity scores."""

    def __init__(self, weights: dict[str, float], logger: logging.Logger | None = None):
        self.weights = weights
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def _similarity(a: float, b: float) -> float:
        diff = abs(float(a) - float(b))
        return max(0.0, 1.0 - diff)

    def score_row(self, current: pd.Series, historical: pd.Series) -> float:
        score = 0.0

        score += self.weights["score"] * self._similarity(
            current["ntis_score"], historical["ntis_score"]
        )
        score += self.weights["probability"] * self._similarity(
            current["probability"], historical["probability"]
        )
        score += self.weights["pcr"] * self._similarity(
            current["pcr"], historical["pcr"]
        )
        score += self.weights["ivr_ivp"] * (
            self._similarity(current["ivr"], historical["ivr"]) +
            self._similarity(current["ivp"], historical["ivp"])
        ) / 2.0

        score += self.weights["pattern"] * (
            1.0 if current["pattern"] == historical["pattern"] else 0.0
        )

        pov = (
            self._similarity(current["price_change_pct"], historical["price_change_pct"]) +
            self._similarity(current["oi_change_pct"], historical["oi_change_pct"]) +
            self._similarity(current["volume_change_pct"], historical["volume_change_pct"])
        ) / 3.0

        score += self.weights["price_oi_volume"] * pov

        return round(score * 100.0, 2)

    def calculate(self, current: pd.Series, history: pd.DataFrame) -> pd.DataFrame:
        results = history.copy()
        results["Similarity"] = history.apply(
            lambda row: self.score_row(current, row), axis=1
        )
        return results.sort_values("Similarity", ascending=False).reset_index(drop=True)
