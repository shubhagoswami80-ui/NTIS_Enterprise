# Baseline Freeze Gate

This gate is deliberately small.

1. `reproduce_w73_baseline.py` reads ONLY:
   `Intraday_W73\00_BASELINE\chronological_validation_corrected.csv`
2. It applies the frozen robust support gate.
3. It extracts the maximum robust candidate.
4. It records the source SHA256.
5. It writes the exact candidate conditions to `strategy_baseline_v1.json`.
6. The test confirms the established 72.093% / 129 / 5 / 45 result.

This is NOT yet live strategy validation. It is the reproducibility/freeze gate.

Once this passes, the next implementation step is to convert the selected candidate's
feature conditions into W73-owned exact V8 feature-engine logic. No old module will be
imported at runtime.
