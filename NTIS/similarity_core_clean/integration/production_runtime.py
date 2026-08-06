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

        similarity_confidence = SimilarityConfidenceCalculator().calculate(
            similarity_result={},
            evidence_scores=evidence_scores
        )

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
            "similarity_confidence": similarity_confidence
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