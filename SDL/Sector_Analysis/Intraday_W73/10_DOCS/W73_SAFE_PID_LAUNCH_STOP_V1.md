# W73 Safe PID Launch/Stop v1

## Objective

W73 must be started and stopped without accidentally terminating another
Python/Streamlit process.

## Runtime

- Dashboard: `11_DASHBOARD\w73_dashboard.py`
- Port: `9005`
- PID record: `11_DASHBOARD\.runtime\w73_dashboard.pid.json`

## Start behavior

The launcher:
1. starts only the W73 Streamlit command;
2. captures the root process PID;
3. records PID, app path, port, Python executable and start time;
4. refuses to create a second W73 instance when the recorded PID is alive.

## Stop behavior

The stopper:
1. reads the recorded PID;
2. resolves the Windows process command line;
3. verifies Streamlit + exact W73 app path + port 9005;
4. refuses to stop the process if identity does not match;
5. walks only descendants of the verified W73 root;
6. never uses broad `python.exe` termination;
7. removes the PID file only after the root process is gone.

## Safety rule

If the PID has been reused by another process, the stopper prints
`REFUSING_TO_STOP_UNVERIFIED_PID` and exits without stopping anything.

Existing SDL/EOD/other Python processes are not targeted by this mechanism.
