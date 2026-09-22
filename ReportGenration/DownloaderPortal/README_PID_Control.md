# Downloader Portal 9001 — PID-controlled launcher replacement

Replace the existing launcher files in:
`E:\NSE_Daily_Analysis\ReportGenration\DownloaderPortal`

Files:
- `start_9001.ps1`
- `stop_9001.ps1`
- `status_9001.ps1`

Safety behavior:
1. Starts Streamlit in the background; the PowerShell prompt returns immediately.
2. Uses the fixed NTIS virtual-environment Python executable.
3. Refuses to start if TCP port 9001 is already occupied by an unrelated process.
4. Stores PID/state in `runtime\9001.process.json`.
5. Stop validates the process command line before terminating anything.
6. Stop terminates only the verified portal process and its descendants.
7. It never uses `taskkill /IM python.exe` and never stops all Python processes.
8. It verifies port 9001 is free before reporting a successful stop.

First use:
- If the foreground 9001 Streamlit process is currently occupying PowerShell, press `Ctrl+C` once to stop that foreground instance.
- Replace the three launcher files.
- From the portal directory run:
  `.\start_9001.ps1`
- Then verify:
  `.\status_9001.ps1`
- Stop only this portal with:
  `.\stop_9001.ps1`

The existing 8506 downloader is not touched by these scripts.
