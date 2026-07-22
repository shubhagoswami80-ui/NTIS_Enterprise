from similarity_core.integration.execution_context import ExecutionContext
from similarity_core.integration.hmme_runtime_executor import HMMERuntimeExecutor
from similarity_core.integration.result_collector import ResultCollector
from similarity_core.integration.functional_gateway import FunctionalGateway

class ProductionRuntime:
    def __init__(self):
        self.context = ExecutionContext()
        self.gateway = FunctionalGateway()

    def run(self):
        executor = HMMERuntimeExecutor(self.gateway)
        result = executor.execute()
        return ResultCollector().collect(result)
