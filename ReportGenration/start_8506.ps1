$ErrorActionPreference = "Stop"

$Python = "E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"
$Root = "E:\NSE_Daily_Analysis\ReportGenration"
$OutputLog = "$Root\streamlit_8506.out.log"
$ErrorLog = "$Root\streamlit_8506.err.log"

if (-not (Test-Path $Python)) {
    Write-Host "ERROR: Python environment not found:"
    Write-Host $Python
    exit 1
}

if (-not (Test-Path "$Root\app.py")) {
    Write-Host "ERROR: app.py not found:"
    Write-Host "$Root\app.py"
    exit 1
}

Set-Location $Root

$existing = Get-NetTCPConnection -LocalPort 8506 -State Listen -ErrorAction SilentlyContinue

if ($existing) {
    Write-Host ""
    Write-Host "Port 8506 is already in use."
    Write-Host "Open: http://localhost:8506"
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "=============================================="
Write-Host " Report Generation - Online Downloader"
Write-Host "=============================================="
Write-Host ""
Write-Host "Python : $Python"
Write-Host "Folder : $Root"
Write-Host "Port   : 8506"
Write-Host ""

$arguments = "-m streamlit run `"$Root\app.py`" --server.port 8506 --server.headless true"

$Process = Start-Process `
    -FilePath $Python `
    -ArgumentList $arguments `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutputLog `
    -RedirectStandardError $ErrorLog `
    -PassThru

Start-Sleep -Seconds 3

$running = Get-NetTCPConnection -LocalPort 8506 -State Listen -ErrorAction SilentlyContinue

if ($running) {
    Write-Host "Report Downloader started successfully."
    Write-Host "Process ID : $($Process.Id)"
    Write-Host "URL        : http://localhost:8506"
    Write-Host ""
}
else {
    Write-Host "ERROR: Streamlit did not start."
    Write-Host ""
    Write-Host "Output log:"
    Write-Host $OutputLog
    Write-Host ""
    Write-Host "Error log:"
    Write-Host $ErrorLog
    Write-Host ""
}