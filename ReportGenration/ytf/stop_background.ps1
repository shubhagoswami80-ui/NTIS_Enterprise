# Stop ONLY the ytf collector recorded in its PID file.
$ErrorActionPreference = "Stop"

$ProjectRoot = "E:\NSE_Daily_Analysis\ReportGenration\ytf"
$ScriptPath  = Join-Path $ProjectRoot "ftd.py"
$RuntimeDir  = Join-Path $ProjectRoot "runtime_control"
$PidFile     = Join-Path $RuntimeDir "ftd.pid"

if (!(Test-Path -LiteralPath $PidFile -PathType Leaf)) {
    Write-Host "No ytf collector PID file found. Nothing stopped."
    exit 0
}

$pidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
[int]$targetPid = 0
if (!([int]::TryParse($pidText, [ref]$targetPid)) -or $targetPid -le 0) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    throw "Invalid PID file. No process was stopped."
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue
if (!$process) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Recorded ytf process is not running."
    exit 0
}

$commandLine = [string]$process.CommandLine
$normalizedCommand = $commandLine.ToLowerInvariant()
$normalizedScript = $ScriptPath.ToLowerInvariant()

if ($normalizedCommand.IndexOf($normalizedScript) -lt 0) {
    throw "Safety check failed: PID $targetPid is not the intended ytf ftd.py process. Nothing was stopped."
}

Stop-Process -Id $targetPid -Force
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "Stopped ONLY ytf collector PID $targetPid."
