
"""
=========================================================
NTIS Historical Similarity Engine
Module      : similarity_ranker.py
Version     : 1.0.0
Release     : R1
Status      : Production Foundation

Public API
----------
SimilarityRanker.rank()
SimilarityRanker.best_match()
=========================================================
"""

from __future__ import annotations

import pandas as pd


class SimilarityRanker:
    """Ranks similarity results and returns the best matches."""

    def __init__(self, top_matches: int = 10, minimum_similarity: float = 60.0):
        self.top_matches = top_matches
        self.minimum_similarity = minimum_similarity

    def rank(self, similarity_df: pd.DataFrame) -> pd.DataFrame:
        if "Similarity" not in similarity_df.columns:
            raise ValueError("Column 'Similarity' not found.")

        ranked = (
            similarity_df[similarity_df["Similarity"] >= self.minimum_similarity]
            .sort_values("Similarity", ascending=False)
            .head(self.top_matches)
            .reset_index(drop=True)
        )

        ranked.insert(0, "Rank", range(1, len(ranked) + 1))
        return ranked

    @staticmethod
    def best_match(ranked_df: pd.DataFrame) -> pd.Series | None:
        if ranked_df.empty:
            return None
        return ranked_df.iloc[0]
