$ErrorActionPreference = "Stop"
$expectedPort=9005
$W73Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidFile = Join-Path $W73Root "11_DASHBOARD\.runtime\w73_dashboard.pid.json"

if (-not (Test-Path $PidFile)) {
    Write-Host "W73_PID_FILE_NOT_FOUND"
    exit 0
}

try {
    $state = Get-Content $PidFile -Raw | ConvertFrom-Json
} catch {
    Write-Host "REFUSING_TO_STOP_INVALID_PID_FILE"
    exit 1
}

$targetPid = [int]$state.pid
if ($targetPid -le 0) {
    Write-Host "REFUSING_TO_STOP_INVALID_PID"
    exit 1
}

$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$targetPid"
if (-not $proc) {
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "W73_PROCESS_NOT_RUNNING"
    exit 0
}

$commandLine = [string]$proc.CommandLine
$exePath = [string]$proc.ExecutablePath

if ($commandLine -notmatch 'Intraday_W73' -or
    $commandLine -notmatch 'w73_dashboard\.py' -or
    $commandLine -notmatch 'streamlit') {
    Write-Host "REFUSING_TO_STOP_UNVERIFIED_PID=$targetPid"
    exit 1
}

$descendantPids = @()
$queue = @($targetPid)

while ($queue.Count -gt 0) {
    $parentPid = [int]$queue[0]
    if ($queue.Count -eq 1) { $queue = @() } else { $queue = @($queue[1..($queue.Count-1)]) }

    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$parentPid")
    foreach ($child in $children) {
        $childPid = [int]$child.ProcessId
        if ($childPid -ne $targetPid -and $descendantPids -notcontains $childPid) {
            $descendantPids += $childPid
            $queue += $childPid
        }
    }
}

foreach ($childPid in ($descendantPids | Sort-Object -Descending)) {
    try { Stop-Process -Id $childPid -Force -ErrorAction Stop } catch {}
}

try {
    Stop-Process -Id $targetPid -Force -ErrorAction Stop
} catch {
    Write-Host "FAILED_TO_STOP_W73_PID=$targetPid"
    exit 1
}

Start-Sleep -Milliseconds 500
$remaining = Get-CimInstance Win32_Process -Filter "ProcessId=$targetPid" -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "W73_STOP_VERIFY_FAILED_PID=$targetPid"
    exit 1
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "W73_STOPPED_PID=$targetPid"


