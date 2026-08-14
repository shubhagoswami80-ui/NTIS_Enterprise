param(
    [ValidateSet("start","stop","restart","status")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Port = 8505
$Url = "http://localhost:$Port/"
$App = Join-Path $ProjectRoot "derivative_signal\app.py"

function Get-PortConnections {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
}

function Get-SdlPython {
    # Prefer the Python from the currently activated environment.
    $activePython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($activePython -and (Test-Path $activePython)) {
        return $activePython
    }

    # Fallback: discover an existing SDL .venv without creating anything.
    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe"),
        (Join-Path (Split-Path -Parent (Split-Path -Parent $ProjectRoot)) ".venv\Scripts\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Could not find an existing Python environment. Activate the existing SDL .venv and run this script again. No environment was created."
}

function Show-Status {
    $connections = Get-PortConnections

    if ($connections) {
        Write-Host ""
        Write-Host "NTIS SDL Decision Signals: RUNNING" -ForegroundColor Green
        Write-Host "URL: $Url"
        Write-Host "Port: $Port"
        $connections | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table
    }
    else {
        Write-Host ""
        Write-Host "NTIS SDL Decision Signals: STOPPED" -ForegroundColor Yellow
        Write-Host "Reserved port: $Port"
    }

    Write-Host ""
    Write-Host "Existing SDL port 8504 is not managed by this script."
}

function Start-DecisionSignals {
    if (-not (Test-Path $App)) {
        throw "Decision Signals app not found: $App"
    }

    $existing = Get-PortConnections
    if ($existing) {
        Write-Host "Decision Signals is already running on $Url" -ForegroundColor Green
        return
    }

    $python = Get-SdlPython

    Set-Location $ProjectRoot

    Write-Host "Starting NTIS SDL Decision Signals..."
    Write-Host "Port: $Port"
    Write-Host "URL : $Url"

    Start-Process `
        -FilePath $python `
        -ArgumentList @(
            "-m", "streamlit", "run", $App,
            "--server.port", $Port,
            "--server.address", "localhost",
            "--server.headless", "true"
        ) `
        -WorkingDirectory $ProjectRoot

    Start-Sleep -Seconds 3

    if (Get-PortConnections) {
        Write-Host "Decision Signals started successfully." -ForegroundColor Green
        Write-Host $Url
    }
    else {
        Write-Warning "Process was launched but port $Port is not listening yet."
        Write-Host "Run: .\derivative_signal.ps1 status"
    }
}

function Stop-DecisionSignals {
    $connections = Get-PortConnections

    if (-not $connections) {
        Write-Host "Decision Signals is already stopped." -ForegroundColor Yellow
        return
    }

    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($processId in $pids) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host "Stopped Decision Signals process $processId." -ForegroundColor Green
        }
        catch {
            Write-Warning "Could not stop process $processId : $($_.Exception.Message)"
        }
    }
}

function Restart-DecisionSignals {
    Stop-DecisionSignals
    Start-Sleep -Seconds 1
    Start-DecisionSignals
}

switch ($Action) {
    "start"   { Start-DecisionSignals }
    "stop"    { Stop-DecisionSignals }
    "restart" { Restart-DecisionSignals }
    "status"  { Show-Status }
}
