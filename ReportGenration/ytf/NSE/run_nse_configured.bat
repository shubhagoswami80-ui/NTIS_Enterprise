@echo off
setlocal
set "PYTHON=E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"
set "NSE_DIR=E:\NSE_Daily_Analysis\ReportGenration\ytf\NSE"

"%PYTHON%" "%NSE_DIR%\nse_configured_runner.py" --config "%NSE_DIR%\nse_config.json" --write-manifest %*
exit /b %ERRORLEVEL%
