$ErrorActionPreference = "Stop"

$Port = 8505
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "No Decision Signals process is listening on port $Port."
    exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $pids) {
    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
        Write-Host "Stopped process $pid on port $Port."
    } catch {
        Write-Warning "Could not stop process $pid : $($_.Exception.Message)"
    }
}
