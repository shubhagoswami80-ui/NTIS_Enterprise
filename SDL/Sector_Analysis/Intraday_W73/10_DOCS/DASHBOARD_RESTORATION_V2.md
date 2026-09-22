# W73 Dashboard Restoration v2

This is the controlled correction after the v1 restoration caused two regression-test failures.

1. The rich v9 trader-board UI is retained.
2. `w73_live_decision_service` is now explicitly imported and invoked for exact V8 live-decision readiness.
3. The safe-stop script retains `$expectedPort=9005` and uses non-reserved PID variable names.
4. No V8 strategy rule, backend contract, source adapter, or production SDL code is changed.
