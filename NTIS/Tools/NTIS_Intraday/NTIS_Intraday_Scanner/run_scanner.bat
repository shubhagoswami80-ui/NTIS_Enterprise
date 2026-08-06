@echo off
title NTIS_Intraday Engineering Scanner

cd /d "%~dp0"

echo.
echo ============================================
echo        NTIS_Intraday Engineering Scanner
echo ============================================
echo.

python ntis_intraday_scanner.py

echo.
echo ============================================
echo Generation Complete
echo ============================================
echo.
pause