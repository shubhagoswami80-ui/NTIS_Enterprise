# Operating Runbook

## Normal day
1. Start existing SDL on its normal port 8504.
2. Start Decision Signals with `start_derivative_signal.ps1`.
3. Open `http://localhost:8505/`.
4. Select today's date.
5. Select the first available source.
6. Process.
7. When the next source arrives, select it and process again.
8. Compare decision changes.

## Stop
Run `stop_derivative_signal.ps1`.

## Status
Run `status_derivative_signal.ps1`.

## Safety
Do not edit the existing SDL launcher or `SDL/app.py` for this project.
Do not run Decision Signals on 8504.
