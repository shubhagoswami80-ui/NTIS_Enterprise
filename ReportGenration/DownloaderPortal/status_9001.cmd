@echo off
set "PORT=9001"
powershell.exe -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; Write-Host '=== Downloader Portal Status ==='; Write-Host 'Port: %PORT%'; if(-not $c){Write-Host 'Status: NOT LISTENING'; exit 0}; Write-Host 'Status: LISTENING'; Write-Host ('Listener PID: ' + $c.OwningProcess); Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess) | Select-Object ProcessId,ParentProcessId,CommandLine | Format-List"
exit /b %errorlevel%
