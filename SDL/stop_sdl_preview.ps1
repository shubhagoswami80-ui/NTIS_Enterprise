$ErrorActionPreference = "Stop"
$Port = 8587
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $connections) { Write-Host "SDL preview is already stopped. Port $Port is free."; exit 0 }
foreach ($item in $connections) {
    $ownerPid = $item.OwningProcess
    if (-not $ownerPid) { continue }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -and $proc.CommandLine -like "*sdl_decision_centre_preview.py*" -and $proc.CommandLine -like "*--server.port $Port*") {
        Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped SDL preview PID $ownerPid on port $Port."
    }
}
Start-Sleep -Milliseconds 700
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Warning "Port $Port is still listening, but no non-SDL process was stopped."
} else { Write-Host "SDL preview stopped. Port $Port is free." }
