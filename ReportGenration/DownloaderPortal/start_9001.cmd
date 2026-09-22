@echo off
set "ROOT=%~dp0"
set "PYTHON=E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"
set "PORT=9001"

if not exist "%PYTHON%" goto :PYERR

powershell.exe -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if($c){Write-Host 'Downloader Portal is already listening on port %PORT% (PID ' $c.OwningProcess ')'; exit 2}" 
if errorlevel 2 exit /b 2

echo Starting Downloader Portal in background...
start "" /b "%PYTHON%" -m streamlit run "%ROOT%app.py" --server.port %PORT% --server.address 127.0.0.1 --server.headless true --server.fileWatcherType none

powershell.exe -NoProfile -Command "$ok=$false; 1..30 | %% { Start-Sleep -Seconds 1; $c=Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if($c){Write-Host 'Downloader Portal started.'; Write-Host 'Port: %PORT%'; Write-Host ('Listener PID: ' + $c.OwningProcess); Write-Host 'URL: http://localhost:%PORT%'; $ok=$true; break } }; if(-not $ok){Write-Host 'ERROR: Downloader Portal did not begin listening on port %PORT% within 30 seconds'; exit 4}"
exit /b %errorlevel%

:PYERR
echo ERROR: Python executable not found:
echo %PYTHON%
exit /b 3
