param(
    [int]$Port = 8504,
    [string]$ProjectRoot = $PSScriptRoot
)

$env:SDL_PROJECT_ROOT = $ProjectRoot
$env:SDL_DASHBOARD_PORT = "$Port"

Set-Location $ProjectRoot

# Use the currently activated environment when available; otherwise use
# the project's .venv if it exists. No absolute NTIS path is assumed.
if (Test-Path "$ProjectRoot\.venv\Scripts\python.exe") {
    $PythonPath = "$ProjectRoot\.venv\Scripts\python.exe"
} else {
    $PythonPath = (Get-Command python).Source
}

Write-Host "Starting SDL Dashboard"
Write-Host "Project Root : $ProjectRoot"
Write-Host "Input Dir    : $env:SDL_INPUT_DIR"
Write-Host "Event Dir    : $env:SDL_EVENT_DIR"
Write-Host "State Dir    : $env:SDL_STATE_DIR"
Write-Host "Log Dir      : $env:SDL_LOG_DIR"
Write-Host "Port         : $Port"

& $PythonPath -m streamlit run app.py --server.port $Port
