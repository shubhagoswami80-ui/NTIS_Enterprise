"""
=========================================================
NTIS Historical Similarity Engine
Module : historical_similarity_engine.py
Version: 1.0.1
Release: HMME-01 Integration

Purpose:
    Adds Candidate Selector stage before similarity
    calculation.

Existing similarity workflow preserved.
=========================================================
"""

from .similarity_loader import SimilarityLoader
from .feature_normalizer import FeatureNormalizer
from .similarity_calculator import SimilarityCalculator
from .similarity_ranker import SimilarityRanker
from .similarity_probability import SimilarityProbability
from .similarity_report import SimilarityReport
from .candidate_selector import CandidateSelector

from Config.similarity_config import (
    FEATURE_WEIGHTS,
    TOP_MATCHES,
    MIN_SIMILARITY,
    CANDIDATE_SELECTOR_CONFIG,
)


class HistoricalSimilarityEngine:

    def __init__(self):

        self.loader = SimilarityLoader()

        self.selector = CandidateSelector(
            score_window=CANDIDATE_SELECTOR_CONFIG["score_window"],
            require_pattern_match=CANDIDATE_SELECTOR_CONFIG[
                "require_pattern_match"
            ],
            require_trade_bias_match=CANDIDATE_SELECTOR_CONFIG[
                "require_trade_bias_match"
            ],
        )

        self.normalizer = FeatureNormalizer()

        self.calculator = SimilarityCalculator(
            FEATURE_WEIGHTS
        )

        self.ranker = SimilarityRanker(
            top_matches=TOP_MATCHES,
            minimum_similarity=MIN_SIMILARITY,
        )

        self.probability = SimilarityProbability()
        self.report = SimilarityReport()


    def run(
        self,
        current_row,
        history_csv,
        summary_output,
        matches_output,
    ):

        history = self.loader.load_csv(history_csv)

        candidates = self.selector.select(
            current_row,
            history,
        )

        current = self.normalizer.prepare_features(
            current_row
        )

        historical = self.normalizer.prepare_features(
            candidates
        )

        scored = self.calculator.calculate(
            current,
            historical,
        )

        ranked = self.ranker.rank(
            scored
        )

        probability = self.probability.calculate(
            ranked
        )

        summary = self.report.build_summary(
            symbol=current_row.get(
                "Symbol",
                "UNKNOWN",
            ),
            probability_result=probability,
            ranked_matches=ranked,
        )

        self.report.export_csv(
            summary,
            summary_output,
        )

        self.report.export_matches(
            ranked,
            matches_output,
        )

        return summary, ranked, probability
