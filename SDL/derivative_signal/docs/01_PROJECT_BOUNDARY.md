# Project Boundary

## Existing SDL
- Owns existing application.
- Owns port 8504.
- Existing `SDL/app.py` remains untouched.
- Existing Straddle Breakout logic remains untouched.

## Decision Signals
- Lives entirely under `SDL/derivative_signal/`.
- Runs independently on port 8505.
- Uses existing SDL services read-only/reuse-only.
- Has its own start/stop/status scripts.
