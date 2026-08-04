# IMPLEMENTATION_STATE

## 1. Current implementation point

The active production integration point is the Historical Intelligence stage in the enterprise pipeline:

- Repository entrypoint: app.py
- Pipeline stage invoked: Historical Intelligence
- Runtime module executed: similarity_core_clean/integration/production_runtime.py

The current runtime chain in `production_runtime.py` is:

1. `ProductionRuntime.run()` creates the runtime context and functional gateway.
2. `HMMERuntimeExecutor(self.gateway).execute()` is called as the initial runtime step.
3. `HMMEHistoricalDataLoader()` loads historical data and evidence.
4. `HistoricalEvidenceScorer()` scores evidence records.
5. `SimilarityConfidenceCalculator()` calculates similarity confidence.
6. `ProbabilityEvidenceEnhancer()` enhances probability output using evidence scores.
7. `HMMEReplayEngine()` and `HMMERealReplayController()` perform replay execution.
8. `HMMEOutcomeCalibration()` validates and calibrates replay results.
9. `HMMELearningBridge()` collects feedback and updates learning state.
10. `ResultCollector()` packages the final runtime result.

## 2. Remaining production work

The repository documentation already identifies the next production sequence:

- Runtime integration: current in-flight work
- Replay integration: next planned step
- Dashboard integration: following replay
- Validation: end-state verification step

From the AI_CONTEXT guidance, the immediate goal is still to complete the live NTIS output integration path while preserving the frozen architecture and avoiding new engines.

## 3. Current dependency graph

app.py
  -> similarity_core_clean.integration.production_runtime
     -> ProductionRuntime
        -> ExecutionContext
        -> FunctionalGateway
           -> LegacyEngineAdapter
           -> SimilarityEngineAdapter
           -> ProbabilityEngineAdapter
           -> CalibrationAdapter
        -> HMMERuntimeExecutor
        -> HMMEHistoricalDataLoader
        -> HistoricalEvidenceScorer
        -> SimilarityConfidenceCalculator
        -> ProbabilityEvidenceEnhancer
        -> HMMEReplayEngine
        -> HMMERealReplayController
        -> HMMEOutcomeCalibration
        -> HMMELearningBridge
        -> ResultCollector

Observed runtime dependency direction:

- app.py orchestrates the enterprise pipeline.
- production_runtime.py is the compatibility layer that activates the historical intelligence runtime.
- FunctionalGateway and adapters provide the bridge into the runtime and engine components.
- Replay, calibration, and learning are all downstream of the historical evidence and similarity scoring step.

## 4. Files that require modification

The files most directly implicated for the remaining production runtime work are:

- similarity_core_clean/integration/production_runtime.py
  - Primary orchestration module for the historical intelligence runtime path.

- similarity_core_clean/integration/functional_gateway.py
  - Central gateway used by the runtime executor to connect adapter-backed components.

- similarity_core_clean/integration/hmme_real_replay_controller.py
  - Replay controller that forwards evidence scores into replay execution.

- similarity_core_clean/integration/hmme_replay_engine.py
  - Replay execution and evaluation contract.

- similarity_core_clean/integration/hmme_learning_bridge.py
  - Learning feedback collection and update path.

- similarity_core_clean/integration/hmme_outcome_calibration.py
  - Outcome validation and calibration step.

- similarity_core_clean/adapters/legacy_engine_adapter.py
- similarity_core_clean/adapters/similarity_engine_adapter.py
- similarity_core_clean/adapters/probability_engine_adapter.py
- similarity_core_clean/adapters/calibration_adapter.py
  - Adapters that supply runtime compatibility and connection readiness for the gateway.

## Notes

- This document is a status-only artifact and does not alter production logic.
- No production code files were modified while creating this state summary.
