# Save as monitor_pcr_volume.ps1
$root = "D:\My-data\Share_P&L\Ichart Data\Screenshot\PCR_Volume_Skew_Output\Current"
$status = Join-Path $root "pcr_volume_skew_live_status.json"
while ($true) {
    Clear-Host
    Write-Host "PCR Volume Pattern Discovery Monitor" -ForegroundColor Cyan
    Write-Host ("Time: " + (Get-Date))
    $p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match "pcr_volume_pattern_discovery.py" }
    if ($p) {
        Write-Host "Process detected:" -ForegroundColor Green
        $p | Select-Object ProcessId, CommandLine | Format-List
    } else {
        Write-Host "No active pattern-discovery process detected." -ForegroundColor Yellow
    }
    if (Test-Path $status) {
        Write-Host "`nLive status:"
        Get-Content $status -Raw
    } else {
        Write-Host "`nLive status file not found."
    }
    Start-Sleep -Seconds 5
}
