
"""
=========================================================
NTIS Historical Similarity Engine
Module      : similarity_report.py
Version     : 1.0.0
Release     : R1
Status      : Production Foundation
=========================================================
"""

from __future__ import annotations

import pandas as pd


class SimilarityReport:
    """Builds a concise report from similarity results."""

    def build_summary(
        self,
        symbol: str,
        probability_result: dict,
        ranked_matches: pd.DataFrame,
    ) -> pd.DataFrame:
        top_similarity = (
            float(ranked_matches.iloc[0]["Similarity"])
            if not ranked_matches.empty
            else 0.0
        )

        summary = {
            "Symbol": symbol,
            "Historical Matches": probability_result.get("matches", 0),
            "Wins": probability_result.get("wins", 0),
            "Losses": probability_result.get("losses", 0),
            "Historical Win %": probability_result.get("win_probability", 0.0),
            "Confidence": probability_result.get("confidence", "LOW"),
            "Top Similarity %": round(top_similarity, 2),
        }

        return pd.DataFrame([summary])

    @staticmethod
    def export_csv(report_df: pd.DataFrame, output_file: str) -> None:
        report_df.to_csv(output_file, index=False)

    @staticmethod
    def export_matches(matches_df: pd.DataFrame, output_file: str) -> None:
        matches_df.to_csv(output_file, index=False)
