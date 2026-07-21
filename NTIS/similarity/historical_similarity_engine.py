# historical_similarity_engine.py
from __future__ import annotations
from pathlib import Path

from similarity_loader import SimilarityLoader
from feature_normalizer import FeatureNormalizer
from similarity_calculator import SimilarityCalculator
from similarity_ranker import SimilarityRanker
from similarity_probability import SimilarityProbability
from similarity_report import SimilarityReport
from similarity_config import SIMILARITY_CONFIG


class HistoricalSimilarityEngine:
    def __init__(self):
        self.loader = SimilarityLoader()
        self.normalizer = FeatureNormalizer()
        self.calculator = SimilarityCalculator(SIMILARITY_CONFIG["weights"])
        self.ranker = SimilarityRanker(
            top_matches=SIMILARITY_CONFIG["top_matches"],
            minimum_similarity=SIMILARITY_CONFIG["minimum_similarity"],
        )
        self.probability = SimilarityProbability()
        self.report = SimilarityReport()

    def run(self, current_row, history_csv, summary_output, matches_output):
        history = self.loader.load_csv(history_csv)
        current = self.normalizer.prepare_features(current_row)
        historical = self.normalizer.prepare_features(history)
        scored = self.calculator.calculate(current, historical)
        ranked = self.ranker.rank(scored)
        probability = self.probability.calculate(ranked)
        summary = self.report.build_summary(
            symbol=current_row.get("Symbol", "UNKNOWN"),
            probability_result=probability,
            ranked_matches=ranked,
        )
        self.report.export_csv(summary, summary_output)
        self.report.export_matches(ranked, matches_output)
        return summary, ranked, probability
