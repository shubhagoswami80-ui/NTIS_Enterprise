$Host.UI.RawUI.WindowTitle = "NTIS_Intraday Engineering Scanner"

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "============================================"
Write-Host " NTIS_Intraday Engineering Scanner"
Write-Host "============================================"
Write-Host ""

python ntis_intraday_scanner.py

Write-Host ""
Write-Host "============================================"
Write-Host " Generation Complete"
Write-Host "============================================"
Write-Host ""

Read-Host "Press ENTER to exit"