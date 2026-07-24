# ============================================================
# NTIS Intraday Dashboard Starter
# ============================================================

$ProjectPath = "E:\NSE_Daily_Analysis\NTIS\Intraday"

$PythonPath = "E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"

$DashboardFile = "intraday_dashboard.py"

$Port = 8502

$PidFile = "$ProjectPath\intraday_dashboard.pid"


# Move to project folder
Set-Location $ProjectPath


# Check existing PID
if (Test-Path $PidFile) {

    $OldPID = Get-Content $PidFile

    try {

        Get-Process -Id $OldPID -ErrorAction Stop

        Write-Host "Intraday Dashboard already running. PID: $OldPID"
        exit

    }
    catch {

        Remove-Item $PidFile

    }
}


Write-Host "Starting NTIS Intraday Dashboard..."



$Process = Start-Process `
    -FilePath $PythonPath `
    -ArgumentList "-m streamlit run $DashboardFile --server.port $Port" `
    -PassThru



$Process.Id | Out-File $PidFile


Write-Host ""
Write-Host "Intraday Dashboard Started"
Write-Host "Port : $Port"
Write-Host "PID  : $($Process.Id)"
Write-Host ""
Write-Host "URL:"
Write-Host "http://localhost:$Port"