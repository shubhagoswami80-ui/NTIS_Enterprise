$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"
$Port = 9001

$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $listenerPid = $listener.OwningProcess
    Write-Host "Downloader Portal appears to be already listening on port $Port (PID $listenerPid)."
    exit 2
}

if (-not (Test-Path $Python)) {
    throw "Python executable not found: $Python"
}

$arguments = "-m streamlit run `"$Root\app.py`" --server.port $Port --server.address 127.0.0.1 --server.headless true --server.fileWatcherType none"

$process = Start-Process -FilePath $Python -ArgumentList $arguments -WorkingDirectory $Root -WindowStyle Hidden -PassThru

Write-Host "Downloader Portal launcher PID: $($process.Id)"
Write-Host "Waiting for port $Port..."

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $listenerPid = $listener.OwningProcess
        Write-Host "Downloader Portal listening on port $Port (PID $listenerPid)."
        Write-Host "http://localhost:$Port"
        exit 0
    }
}

throw "Downloader Portal did not begin listening on port $Port."
