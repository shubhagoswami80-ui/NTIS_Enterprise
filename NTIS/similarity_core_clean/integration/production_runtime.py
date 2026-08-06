"""
NTIS Production Runtime v4.0

Bundle 02 - Historical Intelligence Layer

Adds similarity confidence calculation output.
"""

from similarity_core_clean.integration.execution_context import ExecutionContext
from similarity_core_clean.integration.hmme_runtime_executor import HMMERuntimeExecutor
from similarity_core_clean.integration.result_collector import ResultCollector
from similarity_core_clean.integration.functional_gateway import FunctionalGateway
from similarity_core_clean.reporting.hmme_production_report import HMMEProductionReport
from similarity_core_clean.integration.hmme_learning_bridge import HMMELearningBridge
from similarity_core_clean.integration.hmme_replay_engine import HMMEReplayEngine
from similarity_core_clean.integration.hmme_outcome_calibration import HMMEOutcomeCalibration
from similarity_core_clean.integration.hmme_historical_data_loader import HMMEHistoricalDataLoader
from similarity_core_clean.integration.pattern_repository_engine import PatternRepositoryEngine
from similarity_core_clean.integration.pattern_repository_manager import PatternRepositoryManager
from similarity_core_clean.integration.historical_pattern_intelligence import HistoricalPatternIntelligence
from similarity_core_clean.integration.historical_intelligence_bridge import HistoricalIntelligenceBridge
from similarity_core_clean.integration.eod_similarity_bridge import EODSimilarityBridge
from similarity_core_clean.integration.historical_evidence_aggregator import HistoricalEvidenceAggregator
from similarity_core_clean.integration.historical_evidence_service import HistoricalEvidenceService
from similarity_core_clean.integration.hmme_real_replay_controller import HMMERealReplayController
from similarity_core_clean.integration.historical_evidence_scorer import HistoricalEvidenceScorer
from similarity_core_clean.integration.probability_evidence_enhancer import ProbabilityEvidenceEnhancer
from similarity_core_clean.integration.similarity_confidence_calculator import SimilarityConfidenceCalculator


class ProductionRuntime:

    def __init__(self):
        self.context = ExecutionContext()
        self.gateway = FunctionalGateway()

    def _build_replay_evidence_from_repository(self, repository_records):
        evidence_scores = []

        for record in repository_records or []:
            record_dict = record.to_dict() if hasattr(record, "to_dict") else record if isinstance(record, dict) else None
            if not isinstance(record_dict, dict):
                continue

            normalized_features = record_dict.get("normalized_features") or {}
            evidence_vector = record_dict.get("evidence_vector") or {}

            symbol = record_dict.get("symbol")
            date_value = normalized_features.get("date") or record_dict.get("last_seen")
            if not symbol or not date_value:
                continue

            evidence_score = evidence_vector.get("evidence_score")
            if evidence_score is None:
                confidence = normalized_features.get("confidence")
                if confidence is not None:
                    evidence_score = confidence

            evidence_scores.append({
                "symbol": symbol,
                "date": str(date_value),
                "market_pattern": record_dict.get("pattern_classification"),
                "ntis_score": evidence_vector.get("ntis_score"),
                "probability": evidence_vector.get("probability"),
                "entry": evidence_vector.get("entry"),
                "outcome": record_dict.get("historical_outcome") or evidence_vector.get("outcome"),
                "return_pct": evidence_vector.get("return_pct"),
                "accuracy": evidence_vector.get("accuracy"),
                "confidence": normalized_features.get("confidence") or evidence_vector.get("confidence"),
                "evidence_score": evidence_score,
                "business_pattern_id": record_dict.get("business_pattern_id"),
                "pattern_dna": record_dict.get("pattern_dna"),
            })

        return evidence_scores

    def _normalize_confidence(self, value):
        if value is None:
            return 0.0

        try:
            numeric = float(value)
        except Exception:
            return 0.0

        if numeric <= 0.0:
            return 0.0
        if numeric <= 1.0:
            return numeric
        if numeric <= 100.0:
            return numeric / 100.0
        return 1.0

    def _coerce_float(self, value):
        try:
            return float(value)
        except Exception:
            return None

    def _build_reason_summary(self, replay_strength, historical_success_ratio, evidence_confidence, repository_confidence):
        reasons = []

        if replay_strength >= 75:
            reasons.append("strong replay signal")
        elif replay_strength >= 40:
            reasons.append("moderate replay signal")
        else:
            reasons.append("weak replay signal")

        if historical_success_ratio >= 0.75:
            reasons.append("high historical success")
        elif historical_success_ratio >= 0.4:
            reasons.append("moderate historical success")
        else:
            reasons.append("low historical success")

        if evidence_confidence >= 0.75:
            reasons.append("high evidence confidence")
        elif evidence_confidence >= 0.4:
            reasons.append("moderate evidence confidence")

        if repository_confidence >= 0.75:
            reasons.append("high repository confidence")
        elif repository_confidence >= 0.4:
            reasons.append("moderate repository confidence")

        return "; ".join(reasons)

    def _build_candidate_ranking(self, repository_records, evidence_scores):
        evidence_map = {
            item.get("business_pattern_id"): item
            for item in evidence_scores
            if isinstance(item, dict) and item.get("business_pattern_id")
        }

        candidates = []
        for record in repository_records or []:
            record_dict = record.to_dict() if hasattr(record, "to_dict") else record if isinstance(record, dict) else None
            if not isinstance(record_dict, dict):
                continue

            normalized_features = record_dict.get("normalized_features") or {}
            raw_replay_strength = 0.0
            evidence_item = evidence_map.get(record_dict.get("business_pattern_id"))
            if evidence_item:
                raw_replay_strength = self._coerce_float(evidence_item.get("evidence_score")) or 0.0
            else:
                raw_replay_strength = self._coerce_float(record_dict.get("confidence")) or 0.0

            raw_repository_confidence = self._coerce_float(record_dict.get("confidence")) or 0.0
            raw_historical_success_ratio = self._coerce_float(record_dict.get("success_rate")) or 0.0
            raw_evidence_confidence = self._coerce_float(evidence_item.get("confidence") if evidence_item else normalized_features.get("confidence")) or 0.0
            raw_pattern_confidence = self._coerce_float(normalized_features.get("confidence")) or 0.0

            replay_strength = min(max(raw_replay_strength, 0.0), 100.0)
            repository_confidence = self._normalize_confidence(raw_repository_confidence)
            historical_success_ratio = raw_historical_success_ratio if raw_historical_success_ratio <= 1.0 else min(raw_historical_success_ratio / 100.0, 1.0)
            evidence_confidence = self._normalize_confidence(raw_evidence_confidence)
            pattern_confidence = self._normalize_confidence(raw_pattern_confidence)

            composite_score = (
                0.30 * (replay_strength / 100.0)
                + 0.25 * historical_success_ratio
                + 0.25 * evidence_confidence
                + 0.15 * repository_confidence
                + 0.05 * pattern_confidence
            )

            candidates.append({
                "symbol": record_dict.get("symbol"),
                "business_pattern_id": record_dict.get("business_pattern_id"),
                "pattern_dna": record_dict.get("pattern_dna"),
                "rank": 0,
                "composite_score": round(composite_score, 4),
                "replay_strength": round(replay_strength, 4),
                "historical_success_ratio": round(historical_success_ratio, 4),
                "evidence_confidence": round(evidence_confidence, 4),
                "repository_confidence": round(repository_confidence, 4),
                "reason_summary": self._build_reason_summary(
                    replay_strength,
                    historical_success_ratio,
                    evidence_confidence,
                    repository_confidence,
                ),
            })

        candidates.sort(key=lambda item: (-item["composite_score"], -item["replay_strength"], -item["repository_confidence"]))

        for index, candidate in enumerate(candidates, start=1):
            candidate["rank"] = index

        return candidates

    def run(self):

        runtime_result = HMMERuntimeExecutor(self.gateway).execute()

        report_file = HMMEProductionReport().generate({})

        repository_records = list(self.context.metadata.get("repository_records") or [])
        fingerprint_records = self.context.metadata.get("pattern_fingerprint_records") or []

        if not fingerprint_records:
            fingerprint_records = EODSimilarityBridge().build_fingerprint_payloads()
            self.context.metadata["pattern_fingerprint_records"] = fingerprint_records or []

        if fingerprint_records:
            repository_engine = PatternRepositoryEngine()
            repository_manager = PatternRepositoryManager()

            for fingerprint in fingerprint_records:
                repository_response = repository_engine.create_repository_record(fingerprint)
                repository_record = repository_response.get("repository_record")
                if repository_record is None:
                    continue

                merge_response = repository_manager.manage_repository_record(
                    repository_record,
                    repository_records,
                )
                merged_record = merge_response.get("repository_record")
                if merged_record is None:
                    continue

                existing_index = next(
                    (
                        index
                        for index, item in enumerate(repository_records)
                        if item.get("business_pattern_id") == merged_record.get("business_pattern_id")
                    ),
                    None,
                )

                if existing_index is not None:
                    repository_records[existing_index] = merged_record
                else:
                    repository_records.append(merged_record)

        historical_intelligence = HistoricalPatternIntelligence().analyze(
            repository_records
        )

        bridge_payload = HistoricalIntelligenceBridge().build_intelligence_payload(
            historical_intelligence
        )

        aggregated_evidence = HistoricalEvidenceAggregator().aggregate(
            bridge_payload
        )

        service_output = HistoricalEvidenceService().serve(
            aggregated_evidence
        )

        if service_output.get("service_summary") and isinstance(service_output["service_summary"], dict):
            service_summary = service_output["service_summary"]
            service_summary["symbol"] = self.context.metadata.get("historical_evidence_symbol")
            service_summary["date"] = self.context.metadata.get("historical_evidence_date")
            service_summary["market_pattern"] = self.context.metadata.get("historical_evidence_market_pattern")

        loader = HMMEHistoricalDataLoader()

        historical_data = loader.load()
        evidence_records = loader.load_evidence(
            service_output=service_output
        )

        evidence_scores = HistoricalEvidenceScorer().score(
            evidence_records
        )

        pdna_evidence_scores = self._build_replay_evidence_from_repository(repository_records)
        if pdna_evidence_scores:
            evidence_scores.extend(pdna_evidence_scores)

        similarity_confidence = SimilarityConfidenceCalculator().calculate(
            similarity_result={},
            evidence_scores=evidence_scores
        )

        candidate_ranking = self._build_candidate_ranking(repository_records, evidence_scores)

        probability_enhancement = ProbabilityEvidenceEnhancer().enhance(
            probability_result={},
            evidence_scores=evidence_scores
        )

        replay_engine = HMMEReplayEngine()
        controller = HMMERealReplayController()

        replay_result = controller.run_replay(
            loader,
            replay_engine,
            evidence_scores=evidence_scores
        )

        calibration = HMMEOutcomeCalibration()

        calibration_status = calibration.calibrate(
            calibration.validate_outcome(
                replay_result
            )
        )

        learning = HMMELearningBridge()

        learning_status = learning.update_learning(
            calibration_status
        )

        return ResultCollector().collect({
            "runtime": runtime_result,
            "report": str(report_file),
            "learning": learning_status,
            "replay": replay_result,
            "calibration": calibration_status,
            "historical_records": len(historical_data),
            "evidence_records": len(evidence_scores),
            "repository_summary": repository_records,
            "historical_intelligence": historical_intelligence,
            "historical_evidence": aggregated_evidence.get("historical_evidence") if 'aggregated_evidence' in locals() else None,
            "historical_service_summary": service_output.get("service_summary") if 'service_output' in locals() else None,
            "replay_status": replay_result.get("status") if isinstance(replay_result, dict) else None,
            "calibration_status": calibration_status.get("status") if isinstance(calibration_status, dict) else calibration_status,
            "learning_status": learning_status.get("status") if isinstance(learning_status, dict) else learning_status,
            "probability_enhancement": probability_enhancement,
            "similarity_confidence": similarity_confidence,
            "candidate_ranking": candidate_ranking,
        })
# ==========================================================
# MAIN ENTRY POINT
# ==========================================================

def main():
    """
    Enterprise runtime entry point.

    Used by NTIS app.py to execute the complete
    Historical Intelligence pipeline.
    """
    runtime = ProductionRuntime()

    result = runtime.run()

    print("=" * 70)
    print("HISTORICAL INTELLIGENCE COMPLETED")
    print("=" * 70)

    if isinstance(result, dict):
        print(f"Historical Records : {result.get('historical_records', 0)}")
        print(f"Evidence Records   : {result.get('evidence_records', 0)}")

    return result


if __name__ == "__main__":
    main()