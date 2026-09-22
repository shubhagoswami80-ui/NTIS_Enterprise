$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$expectedPort=9005
$pidFile = Join-Path $root "11_DASHBOARD\.runtime\w73_dashboard.pid.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "W73 dashboard PID file not found. Nothing to stop."
    exit 0
}

try {
    $record = Get-Content -Raw -Path $pidFile | ConvertFrom-Json
} catch {
    throw "Unable to read W73 PID file: $pidFile"
}

if (-not $record.pid) {
    throw "W73 PID file does not contain a PID: $pidFile"
}

if ($record.port -and ([int]$record.port -ne $expectedPort)) {
    throw "REFUSING_TO_STOP_UNEXPECTED_PORT: recorded port=$($record.port), expected port=$expectedPort"
}

$targetPid = [int]$record.pid

try {
    $process = Get-Process -Id $targetPid -ErrorAction Stop
} catch {
    Remove-Item $pidFile -Force
    Write-Host "W73 dashboard process is not running. Stale PID file removed."
    exit 0
}

$commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$targetPid" -ErrorAction SilentlyContinue).CommandLine

if (-not $commandLine) {
    throw "REFUSING_TO_STOP_UNVERIFIED_PID: command line unavailable for PID $targetPid"
}

$dashboard = Join-Path $root "11_DASHBOARD\w73_dashboard.py"

if ($commandLine -notlike "*$dashboard*") {
    throw "REFUSING_TO_STOP_UNVERIFIED_PID: PID $targetPid is not the W73 dashboard process"
}

if ($commandLine -notlike "*--server.port*") {
    throw "REFUSING_TO_STOP_UNVERIFIED_PID: PID $targetPid is not a verified Streamlit W73 process"
}

if ($commandLine -notlike "*$expectedPort*") {
    throw "REFUSING_TO_STOP_UNVERIFIED_PID: PID $targetPid is not running on port $expectedPort"
}

Stop-Process -Id $targetPid -Force
Remove-Item $pidFile -Force

Write-Host "W73 dashboard stopped. PID=$targetPid Port=$expectedPort"
