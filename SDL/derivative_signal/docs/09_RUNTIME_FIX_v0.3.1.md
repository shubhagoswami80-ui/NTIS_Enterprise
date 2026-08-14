# Runtime Fix v0.3.1

The launcher previously assumed a fixed `.venv` location. That assumption is removed.

Launcher behavior:
1. Use the currently active `python.exe`.
2. Otherwise search known existing SDL `.venv` locations.
3. Never create a virtual environment.
4. Continue to manage only port 8505.
5. Existing SDL port 8504 remains outside the script's scope.

Normal operator workflow:

```powershell
cd E:\NSE_Daily_Analysis\SDL\derivative_signal\scripts
.\derivative_signal.ps1 start
```
