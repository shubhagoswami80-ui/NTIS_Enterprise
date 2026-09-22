$ErrorActionPreference = "Stop"
$Port = 9001

$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
    Write-Host "Downloader Portal is not listening on port $Port."
    exit 0
}

$listenerPid = [int]$listener.OwningProcess
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerPid"

if (-not $proc) {
    Write-Host "Listener PID $listenerPid no longer exists."
    exit 0
}

$cmd = [string]$proc.CommandLine
Write-Host "Listener PID: $listenerPid"
Write-Host "Command: $cmd"

$verified = $cmd -match "DownloaderPortal" -and
            $cmd -match "streamlit\s+run" -and
            $cmd -match "app\.py"

if (-not $verified) {
    Write-Host "REFUSED: listener PID $listenerPid does not match the Downloader Portal."
    Write-Host "No process was terminated."
    exit 5
}

Write-Host "Stopping verified Downloader Portal process tree..."
& taskkill.exe /PID $listenerPid /T /F | Out-Host
Start-Sleep -Seconds 2

$remaining = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($remaining) {
    throw "Port $Port is still occupied."
}

Write-Host "Downloader Portal stopped. Port $Port is free."
