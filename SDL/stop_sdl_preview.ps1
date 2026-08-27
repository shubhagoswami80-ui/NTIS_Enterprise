# NTIS SDL Preview - Stop
# Stops ONLY the SDL preview process tree owning port 8587.

$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8587
$Runtime = Join-Path $AppDir ".sdl_preview_runtime"
$PidFile = Join-Path $Runtime "sdl_preview.pid"

function Get-PortOwners {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($c) { return @($c | Select-Object -ExpandProperty OwningProcess -Unique) }
    return @()
}

function Is-SdlPreviewProcess($proc) {
    if (-not $proc -or -not $proc.CommandLine) { return $false }
    return (
        $proc.Name -match "(?i)^python(?:\.exe)?$" -and
        $proc.CommandLine -match "(?i)streamlit" -and
        $proc.CommandLine -match "(?i)sdl_decision_centre_preview\.py" -and
        $proc.CommandLine -match "(?i)--server\.port(?:=|\s+)8587"
    )
}

function Stop-Tree([int]$RootPid) {
    $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ParentProcessId -eq $RootPid } |
        Select-Object -ExpandProperty ProcessId
    foreach ($childPid in $children) {
        Stop-Tree -RootPid $childPid
    }
    Stop-Process -Id $RootPid -Force -ErrorAction SilentlyContinue
}

$owners = Get-PortOwners
if ($owners.Count -eq 0) {
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
    Write-Host "SDL preview is already stopped. Port $Port is free."
    exit 0
}

$stoppedAny = $false
foreach ($ownerPid in $owners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
    if (Is-SdlPreviewProcess $proc) {
        Stop-Tree -RootPid $ownerPid
        $stoppedAny = $true
        Write-Host "Stopped SDL preview process tree rooted at PID $ownerPid."
    } else {
        Write-Warning "Port $Port is owned by PID $ownerPid, but it is not verified as SDL preview. No process was stopped for safety."
        if ($proc) { Write-Host "Command line: $($proc.CommandLine)" }
    }
}

Start-Sleep -Milliseconds 800
$remaining = Get-PortOwners

if ($remaining.Count -eq 0) {
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
    Write-Host "SDL preview stopped. Port $Port is free."
} elseif ($stoppedAny) {
    Write-Warning "SDL preview was stopped, but port $Port is still listening. Remaining PID(s): $($remaining -join ', ')"
} else {
    Write-Warning "Port $Port remains in use by an unverified process."
}
