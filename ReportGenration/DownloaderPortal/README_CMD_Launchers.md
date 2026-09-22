# Downloader Portal 9001 — CMD launchers

Use these `.cmd` files instead of invoking the PowerShell scripts directly.

Start:
    start_9001.cmd

Stop:
    stop_9001.cmd

Status:
    status_9001.cmd

The CMD wrappers invoke the existing PowerShell scripts in a separate PowerShell process with a process-scoped execution-policy setting. They do not modify the Windows execution policy.

The actual PID/port safety logic remains in:
- start_9001.ps1
- stop_9001.ps1
- status_9001.ps1

Therefore:
- no global Python termination
- no `taskkill /IM python.exe`
- no stopping an unrelated process on port 9001
- PID and command-line verification remain enforced
- start returns to the CMD/PowerShell prompt immediately after launching the portal

Deployment:
Copy these three `.cmd` files into:
E:\NSE_Daily_Analysis\ReportGenration\DownloaderPortal

Keep the corresponding `.ps1` files from the previous bundle in the same folder.
