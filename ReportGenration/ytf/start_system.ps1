$ErrorActionPreference='Stop'
$Root='E:\NSE_Daily_Analysis\ReportGenration\ytf'
$Py='E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe'
$Runtime=Join-Path $Root 'runtime_control'
$Collector=Join-Path $Root 'ftd.py'
$Pid=Join-Path $Runtime 'ftd.pid'
if(!(Test-Path $Collector)){throw "Missing collector: $Collector"}
if(!(Test-Path $Py)){throw "Missing Python: $Py"}
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
if(Test-Path $Pid){$old=(Get-Content $Pid -Raw).Trim(); [int]$n=0; if([int]::TryParse($old,[ref]$n)){ $p=Get-CimInstance Win32_Process -Filter "ProcessId = $n" -ErrorAction SilentlyContinue; if($p -and ([string]$p.CommandLine).ToLower().Contains($Collector.ToLower())){Write-Host "YTF collector already running. PID: $n"; exit 0}}; Remove-Item $Pid -Force -ErrorAction SilentlyContinue}
$o=Join-Path $Runtime 'ftd_stdout.log'; $e=Join-Path $Runtime 'ftd_stderr.log'
$p=Start-Process -FilePath $Py -ArgumentList @('-u',$Collector) -WorkingDirectory $Root -RedirectStandardOutput $o -RedirectStandardError $e -WindowStyle Hidden -PassThru
Set-Content $Pid $p.Id -Encoding ASCII
Start-Sleep -Milliseconds 800
if(!(Get-Process -Id $p.Id -ErrorAction SilentlyContinue)){Remove-Item $Pid -Force -ErrorAction SilentlyContinue; throw "Collector exited. Check $e"}
Write-Host "YTF system started: collector PID $($p.Id)"
Write-Host "Report generation remains on-demand because generate_report.py is a one-shot script."
