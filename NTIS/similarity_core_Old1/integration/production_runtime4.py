from similarity_core.integration.execution_context import ExecutionContext
from similarity_core.integration.hmme_runtime_executor import HMMERuntimeExecutor
from similarity_core.integration.result_collector import ResultCollector
from similarity_core.integration.functional_gateway import FunctionalGateway
from similarity_core.integration.ntis_data_bridge import NTISDataBridge
from similarity_core.reporting.hmme_production_report import HMMEProductionReport
from similarity_core.integration.hmme_learning_bridge import HMMELearningBridge
from similarity_core.integration.hmme_replay_engine import HMMEReplayEngine
from similarity_core.integration.hmme_outcome_calibration import HMMEOutcomeCalibration
from similarity_core.integration.hmme_historical_data_loader import HMMEHistoricalDataLoader
from similarity_core.integration.hmme_historical_replay_adapter import HMMEHistoricalReplayAdapter


class ProductionRuntime:

    def __init__(self):
        self.context = ExecutionContext()
        self.gateway = FunctionalGateway()

    def run(self):

        runtime_result = HMMERuntimeExecutor(self.gateway).execute()

        data = NTISDataBridge().load_data()
        report_file = HMMEProductionReport().generate(data)

        learning = HMMELearningBridge()
        learning_status = learning.update_learning(
            learning.collect_feedback()
        )

        history = HMMEHistoricalDataLoader()
        historical_data = history.load()

        adapter = HMMEHistoricalReplayAdapter()
        replay_input = adapter.prepare_replay(historical_data)

        replay = HMMEReplayEngine()
        replay_status = replay.evaluate(
            replay.replay(historical_data)
        )

        calibration = HMMEOutcomeCalibration()
        calibration_status = calibration.calibrate(
            calibration.validate_outcome()
        )

        return ResultCollector().collect({
            "runtime": runtime_result,
            "report": str(report_file),
            "learning": learning_status,
            "replay": replay_status,
            "calibration": calibration_status,
            "historical": replay_input
        })
