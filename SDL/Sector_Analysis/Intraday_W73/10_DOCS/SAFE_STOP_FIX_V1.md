# W73 Safe Stop Fix v1

Fixes a PowerShell reserved-variable collision in the W73 stop script.

The previous script used `$pid` as a loop variable. PowerShell reserves `$PID` as an automatic read-only variable, causing the stop script to terminate before performing its verification.

This bundle changes internal PID variable names to `targetPid`, `parentPid`, and `childPid`.

Safety intent remains fail-closed:
- reads the W73 PID state file;
- verifies the target process;
- requires W73 root / `w73_dashboard.py` / Streamlit markers;
- stops only the verified W73 process tree;
- refuses an unverified PID;
- verifies the target process exited.
