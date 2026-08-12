# SDL Change Record

## v1.0 — Initial Phase-1 implementation package
Created:
- config.py
- app.py
- run_snapshot.py
- sdl/source_loader.py
- sdl/straddle_calculator.py
- sdl/event_detector.py
- sdl/storage.py
- sdl/pipeline.py
- tests/test_straddle_calculator.py
- tests/test_event_detector.py
- docs/01_IMPLEMENTATION_NOTE.md
- docs/02_DATA_FLOW.md

Purpose:
Initial Phase-1 execution bundle following the frozen strategy and roadmap.

Important:
No existing NTIS EOD/Intraday file is modified by this package.


## v1.1 — Dynamic runtime locations
Changed:
- config.py
- sdl/pipeline.py
- app.py
- README.md

Created:
- config.env.example
- start_sdl_dashboard.ps1
- docs/04_RUNTIME_CONFIGURATION.md

Purpose:
Remove machine-specific path assumptions. Input, event, state, log and dashboard runtime locations are configurable through environment variables or launcher parameters.

## v1.2 — Fixed daily Open straddle model
Changed: straddle_calculator.py, pipeline.py, event_detector.py, tests/test_straddle_calculator.py
Created: docs/04_DATA_CONTRACT.md
Decision: Open is the fixed daily ATM/strike reference; current straddle = Open × current ATM Straddle % / 100; base is frozen for the trading day; breakout is strictly >20%.
