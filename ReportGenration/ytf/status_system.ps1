$Root='E:\NSE_Daily_Analysis\ReportGenration\ytf'; $Script=Join-Path $Root 'ftd.py'; $Pid=Join-Path (Join-Path $Root 'runtime_control') 'ftd.pid'
if(!(Test-Path $Pid)){Write-Host 'YTF collector: NOT RUNNING'; exit 1}
[int]$n=0; if(![int]::TryParse((Get-Content $Pid -Raw).Trim(),[ref]$n)){Write-Host 'YTF collector: INVALID PID'; exit 1}
$p=Get-CimInstance Win32_Process -Filter "ProcessId = $n" -ErrorAction SilentlyContinue
if($p -and ([string]$p.CommandLine).ToLower().Contains($Script.ToLower())){Write-Host "YTF collector: RUNNING (PID $n)"}else{Write-Host 'YTF collector: NOT RUNNING'}
Write-Host 'Report generator: ON-DEMAND (not a persistent process)'
