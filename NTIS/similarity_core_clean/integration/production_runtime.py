from similarity_core.integration.execution_context import ExecutionContext
from similarity_core.integration.hmme_runtime_executor import HMMERuntimeExecutor
from similarity_core.integration.result_collector import ResultCollector
from similarity_core.integration.functional_gateway import FunctionalGateway
from similarity_core.reporting.hmme_production_report import HMMEProductionReport
from similarity_core.integration.hmme_learning_bridge import HMMELearningBridge
from similarity_core.integration.hmme_replay_engine import HMMEReplayEngine
from similarity_core.integration.hmme_outcome_calibration import HMMEOutcomeCalibration
from similarity_core.integration.hmme_historical_data_loader import HMMEHistoricalDataLoader
from similarity_core.integration.hmme_historical_replay_adapter import HMMEHistoricalReplayAdapter
from similarity_core.integration.hmme_real_replay_controller import HMMERealReplayController


class ProductionRuntime:

    def __init__(self):
        self.context = ExecutionContext()
        self.gateway = FunctionalGateway()

    def run(self):

        runtime_result = HMMERuntimeExecutor(self.gateway).execute()

        report_file = HMMEProductionReport().generate({})

        learning = HMMELearningBridge()
        learning_status = learning.update_learning(
            learning.collect_feedback()
        )

        loader = HMMEHistoricalDataLoader()
        historical_data = loader.load()

        controller = HMMERealReplayController()
        replay_engine = HMMEReplayEngine()

        replay_result = controller.run_replay(
            loader,
            replay_engine
        )

        calibration = HMMEOutcomeCalibration()
        calibration_status = calibration.calibrate(
            calibration.validate_outcome()
        )

        return ResultCollector().collect({
            "runtime": runtime_result,
            "report": str(report_file),
            "learning": learning_status,
            "replay": replay_result,
            "calibration": calibration_status,
            "historical_records": len(historical_data)
        })
