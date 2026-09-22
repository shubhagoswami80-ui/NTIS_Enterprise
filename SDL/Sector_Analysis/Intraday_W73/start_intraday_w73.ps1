$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir
python -m streamlit run app.py --server.port 9005 --server.headless true --browser.gatherUsageStats false
