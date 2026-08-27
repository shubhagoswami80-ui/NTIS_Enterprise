# NTIS SDL - Stop
# Stops ONLY the SDL production process tree owning port 8504.
# Never stops an unrelated process just because it uses the port.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8504
$RuntimeDir = Join-Path $ProjectRoot ".sdl_runtime"
$PidFile = Join-Path $RuntimeDir "sdl.pid"

function Get-PortOwners {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($c) { return @($c | Select-Object -ExpandProperty OwningProcess -Unique) }
    return @()
}

function Get-ProcessInfo([int]$ProcessId) {
    return Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
}

function Is-SdlProcess($proc) {
    if (-not $proc -or -not $proc.CommandLine) { return $false }
    return (
        $proc.Name -match "(?i)^python(?:\.exe)?$" -and
        $proc.CommandLine -match "(?i)streamlit" -and
        $proc.CommandLine -match "(?i)\bapp\.py\b" -and
        $proc.CommandLine -match "(?i)--server\.port(?:=|\s+)8504"
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
    Write-Host "SDL is already stopped. Port $Port is free."
    exit 0
}

$stoppedAny = $false

foreach ($ownerPid in $owners) {
    $proc = Get-ProcessInfo $ownerPid
    if (Is-SdlProcess $proc) {
        Stop-Tree -RootPid $ownerPid
        $stoppedAny = $true
        Write-Host "Stopped SDL process tree rooted at PID $ownerPid."
    } else {
        Write-Warning "Port $Port is owned by PID $ownerPid, but it is not verified as SDL. No process was stopped for safety."
        if ($proc) { Write-Host "Command line: $($proc.CommandLine)" }
    }
}

Start-Sleep -Milliseconds 800
$remaining = Get-PortOwners

if ($remaining.Count -eq 0) {
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
    Write-Host "SDL stopped. Port $Port is free."
} elseif ($stoppedAny) {
    Write-Warning "SDL process was stopped, but port $Port is still listening. Remaining PID(s): $($remaining -join ', ')"
} else {
    Write-Warning "Port $Port remains in use by an unverified process."
}
