$ErrorActionPreference = "Stop"

$connections = Get-NetTCPConnection -LocalPort 8506 -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "Nothing is running on port 8506."
    exit 0
}

$processIds = $connections |
    Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $processIds) {

    try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "Stopped process $processId"
    }
    catch {
        Write-Host "Could not stop process $processId : $($_.Exception.Message)"
    }
}

Start-Sleep -Seconds 1

$remaining = Get-NetTCPConnection -LocalPort 8506 -State Listen -ErrorAction SilentlyContinue

if ($remaining) {
    Write-Host ""
    Write-Host "WARNING: Port 8506 is still in use."
}
else {
    Write-Host ""
    Write-Host "Port 8506 is free."
    Write-Host "Report Downloader stopped."
}