# Downloader Portal 9001 - status/diagnostic
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 9001
$StateFile = Join-Path $Root "runtime\9001.process.json"

try {
    $connection = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction Stop |
        Select-Object -First 1
} catch {
    $connection = $null
}

if ($connection) {
    $listenerProcessId = [int]$connection.OwningProcess
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerProcessId" -ErrorAction SilentlyContinue
    Write-Host "Port: $Port"
    Write-Host "Listener PID: $listenerProcessId"
    if ($processInfo) {
        Write-Host "Parent PID: $($processInfo.ParentProcessId)"
        Write-Host "Command: $($processInfo.CommandLine)"
    }
} else {
    Write-Host "Port $Port : FREE"
}

if (Test-Path $StateFile) {
    Write-Host ""
    Write-Host "State file:"
    Get-Content $StateFile
} else {
    Write-Host ""
    Write-Host "State file: not present"
}
