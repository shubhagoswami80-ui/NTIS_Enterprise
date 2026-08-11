# ============================================================
# NTIS Intraday Dashboard Stopper
# ============================================================

$ProjectPath = "E:\NSE_Daily_Analysis\NTIS\Intraday"

$PidFile = "$ProjectPath\intraday_dashboard.pid"


Set-Location $ProjectPath


if (!(Test-Path $PidFile)) {

    Write-Host "Intraday Dashboard is not running."
    exit

}


$dashboardPID = Get-Content $PidFile


try {

    Get-Process -Id $dashboardPID -ErrorAction Stop

    Stop-Process -Id $dashboardPID -Force

    Write-Host ""
    Write-Host "Intraday Dashboard stopped"
    Write-Host "PID : $dashboardPID"

}
catch {

    Write-Host ""
    Write-Host "Dashboard process not found."
    Write-Host "Cleaning old PID file."

}


Remove-Item $PidFile -Force