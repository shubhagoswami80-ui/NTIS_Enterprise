$ErrorActionPreference = "Stop"

$SdlRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Port = 8505
$App = Join-Path $SdlRoot "derivative_signal\app.py"

$VenvCandidates = @(
    (Join-Path $SdlRoot ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path -Parent $SdlRoot) ".venv\Scripts\python.exe")
)

$Python = $null
foreach ($candidate in $VenvCandidates) {
    if (Test-Path $candidate) {
        $Python = $candidate
        break
    }
}

if (-not $Python) {
    throw "Could not find the existing SDL .venv Python. No environment was created or changed."
}

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Decision Signals is already listening on port $Port."
    Write-Host "Open http://localhost:$Port/"
    exit 0
}

Set-Location $SdlRoot

Write-Host "Starting NTIS SDL Decision Signals on port $Port ..."
Start-Process `
    -FilePath $Python `
    -ArgumentList @(
        "-m", "streamlit", "run", $App,
        "--server.port", $Port,
        "--server.address", "localhost",
        "--server.headless", "true"
    ) `
    -WorkingDirectory $SdlRoot

Start-Sleep -Seconds 2
Write-Host "Decision Signals URL: http://localhost:$Port/"
