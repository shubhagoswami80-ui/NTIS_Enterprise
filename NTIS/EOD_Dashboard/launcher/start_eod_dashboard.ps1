# NTIS EOD Dashboard Launcher V3
# Uses project virtual environment directly

$ntisRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Set-Location $ntisRoot

$streamlitExe = Join-Path $ntisRoot ".venv\Scripts\streamlit.exe"

$logDir = Join-Path $ntisRoot "EOD_Dashboard\logs"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = Join-Path $logDir "eod_dashboard.log"
$errorLogFile = Join-Path $logDir "eod_dashboard_error.log"

Start-Process `
    $streamlitExe `
    -ArgumentList "run EOD_Dashboard\app\dashboard_app.py --server.port 8503" `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errorLogFile `
    -WindowStyle Hidden

Write-Host "NTIS EOD Dashboard started on port 8503"
Write-Host "URL: http://localhost:8503"
