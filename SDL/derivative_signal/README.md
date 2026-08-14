# NTIS SDL — Decision Signals v0.3

## Project boundary

Everything in this new project lives under:

`SDL/derivative_signal/`

Do **not** replace or modify:

`SDL/app.py`

The existing SDL remains the owner of port **8504**.

This project is designed to run separately on port **8505**.

## Start

Run the supplied PowerShell launcher:

`scripts\start_derivative_signal.ps1`

Expected URL:

`http://localhost:8505/`

## Stop

Run:

`scripts\stop_derivative_signal.ps1`

The stop script only targets the process started on port 8505.

## User workflow

1. Start existing SDL normally.
2. Start Decision Signals separately.
3. Open http://localhost:8505/
4. Select Trading Date.
5. Select the day's source workbook.
6. Press Process Selected Data.
7. Review decision-oriented candidates.
8. When a newer source arrives, select it and process again.
9. Use Historical Replay later to validate the signal layer against a sequence of saved source files.

## Data philosophy

Minimum dependency:
- Symbol
- OHLC
- OI Chg %
- CE OI change
- PE OI change
- PE-CE OI change

The current implementation does not infer or rename `OI Chg %` as explicit Futures OI.

No P&L, automatic execution, probability score, or changes to Straddle Breakout are included in v0.3.


## Preferred operator control

Use `scripts\derivative_signal.ps1`:

`.\derivative_signal.ps1 start`
`.\derivative_signal.ps1 stop`
`.\derivative_signal.ps1 restart`
`.\derivative_signal.ps1 status`

This script manages only port 8505. It does not manage or stop the existing SDL on port 8504.


## Environment behavior

The operator script first uses the currently active `python.exe`. If no Python is
active, it searches for an existing SDL `.venv` in expected parent locations.
It never creates or modifies a virtual environment.
