# NTIS EOD Dashboard Stop Script V4
# Stops Streamlit process tree using port 8503 owner PID

$port = 8503

$processes = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique

if ($processes) {

    foreach ($processId in $processes) {

        Write-Host "Stopping process tree PID:" $processId

        Get-CimInstance Win32_Process -Filter "ParentProcessId=$processId" |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }

    Write-Host "NTIS EOD Dashboard stopped"
}
else {
    Write-Host "No EOD Dashboard process found on port 8503"
}
