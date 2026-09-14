$ErrorActionPreference='Stop'
$Root='E:\NSE_Daily_Analysis\ReportGenration\ytf'; $Script=Join-Path $Root 'ftd.py'; $Pid=Join-Path (Join-Path $Root 'runtime_control') 'ftd.pid'
if(!(Test-Path $Pid)){Write-Host 'YTF collector is not running.'; exit 0}
[int]$n=0; $v=(Get-Content $Pid -Raw).Trim(); if(![int]::TryParse($v,[ref]$n)){Remove-Item $Pid -Force; throw 'Invalid collector PID file.'}
$p=Get-CimInstance Win32_Process -Filter "ProcessId = $n" -ErrorAction SilentlyContinue
if($p -and ([string]$p.CommandLine).ToLower().Contains($Script.ToLower())){Stop-Process -Id $n -Force; Write-Host "Stopped YTF collector PID $n."} else {Write-Host 'Recorded collector process not found; no unrelated process stopped.'}
Remove-Item $Pid -Force -ErrorAction SilentlyContinue
