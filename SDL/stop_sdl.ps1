$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = $ScriptDir
$PidFile = Join-Path $ProjectRoot ".sdl_runtime\sdl.pid"

$connections = Get-NetTCPConnection -LocalPort 8504 -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "SDL is not running on port 8504."
    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $pids) {
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop

        if ($proc.Name -match "^python(\.exe)?$" -and
            $proc.CommandLine -match "streamlit" -and
            $proc.CommandLine -match "--server\.port\s+8504") {

            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host "SDL stopped. PID: $processId"
        }
        else {
            Write-Warning "PID $processId is listening on port 8504 but does not appear to be SDL Streamlit."
            Write-Warning "No process was stopped for safety."
            Write-Host "Command line found: $($proc.CommandLine)"
        }
    }
    catch {
        Write-Warning "Could not safely inspect/stop PID $processId. $($_.Exception.Message)"
    }
}

Start-Sleep -Milliseconds 500

$remaining = Get-NetTCPConnection -LocalPort 8504 -State Listen -ErrorAction SilentlyContinue

if (-not $remaining) {
    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Port 8504 is free."
}
else {
    Write-Warning "Port 8504 is still in use."
}