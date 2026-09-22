# Launcher 04

Fixes the PowerShell `$PID` automatic-variable collision found in launcher 03.

The original helper parameter `$Pid` was invalid because PowerShell variable names are case-insensitive and `$PID` is a built-in read-only automatic variable.

All affected parameters/local variables have been renamed to `ProcessId`-style names.

Replace:
- start_9001.ps1
- stop_9001.ps1
- status_9001.ps1

Then run normally:
`.\start_9001.ps1`

No execution-policy bypass is required if the files have already been unblocked.
