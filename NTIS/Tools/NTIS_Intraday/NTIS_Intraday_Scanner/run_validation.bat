@echo off
title NTIS_Intraday Scanner Validation

cd /d "%~dp0"

python validate_scanner.py

echo.
pause