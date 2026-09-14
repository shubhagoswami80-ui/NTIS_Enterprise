# Check ONLY the ytf collector.
$ProjectRoot = "E:\NSE_Daily_Analysis\ReportGenration\ytf"
$ScriptPath  = Join-Path $ProjectRoot "ftd.py"
$PidFile     = Join-Path (Join-Path $ProjectRoot "runtime_control") "ftd.pid"

if (!(Test-Path -LiteralPath $PidFile -PathType Leaf)) {
    Write-Host "NOT RUNNING - PID file does not exist."
    exit 1
}

$pidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
[int]$targetPid = 0
if (!([int]::TryParse($pidText, [ref]$targetPid)) -or $targetPid -le 0) {
    Write-Host "NOT RUNNING - invalid PID file."
    exit 1
}

$p = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue
if (!$p) {
    Write-Host "NOT RUNNING - recorded process does not exist."
    exit 1
}

if ([string]$p.CommandLine -like "*$ScriptPath*") {
    Write-Host "RUNNING - ytf collector PID $targetPid"
    $p | Select-Object ProcessId, CommandLine
    exit 0
}

Write-Host "NOT RUNNING - PID belongs to another process; no action taken."
exit 1
