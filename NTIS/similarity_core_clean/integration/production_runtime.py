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

        loader = HMMEHistoricalDataLoader()

        historical_data = loader.load()
        evidence_records = loader.load_evidence()

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
            learning.collect_feedback()
        )

        return ResultCollector().collect({
            "runtime": runtime_result,
            "report": str(report_file),
            "learning": learning_status,
            "replay": replay_result,
            "calibration": calibration_status,
            "historical_records": len(historical_data),
            "evidence_records": len(evidence_scores),
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