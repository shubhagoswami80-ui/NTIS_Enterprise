# Handover v0.3

## Current state
Separate Decision Signals project prepared under `SDL/derivative_signal`.

## Runtime
Existing SDL: port 8504.
Decision Signals: port 8505.

## Files
- app.py: new dashboard entry
- dashboard.py: UI and manual processing
- signal_engine.py: current evidence/state rules
- historical_replay.py: replay validation
- data_adapter.py: minimal normalization
- scripts/: start, stop, status
- docs/: architecture, flow, roadmap, runbook

## Not changed
- SDL/app.py
- existing Straddle Breakout pipeline
- existing 8504 runtime

## Immediate validation
Run the start script, process today's first source, then process the next source. Capture one screenshot after the second processing.

Do not add new logic until this runtime and data-flow validation is complete.
