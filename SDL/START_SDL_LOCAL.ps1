$ErrorActionPreference = "Stop"

# This script lives directly under E:\NSE_Daily_Analysis\SDL.
# Do NOT append an extra "\SDL" to PSScriptRoot.
$SDL_ROOT = (Resolve-Path $PSScriptRoot).Path
$APP = Join-Path $SDL_ROOT "app.py"

if (-not (Test-Path -LiteralPath $APP -PathType Leaf)) {
    throw "SDL app.py not found: $APP"
}

# The application is bounded to SDL for its own writes. Established upstream
# data roots remain read-only inputs and are configured by SDL/config.py.
$env:SDL_PROJECT_ROOT = $SDL_ROOT

# Prefer the Python interpreter already active in the user's environment.
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    throw "Python was not found in the current environment. Activate the project .venv first."
}
$python = $pythonCommand.Source

Push-Location $SDL_ROOT
try {
    & $python -m streamlit run $APP --server.port 8504
    if ($LASTEXITCODE -ne 0) {
        throw "SDL Streamlit exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
