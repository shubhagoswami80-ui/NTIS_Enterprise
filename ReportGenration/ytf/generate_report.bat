@echo off
set ROOT=E:\NSE_Daily_Analysis\ReportGenration\ytf
set PY=E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe
"%PY%" "%ROOT%\generate_report.py"
pause
