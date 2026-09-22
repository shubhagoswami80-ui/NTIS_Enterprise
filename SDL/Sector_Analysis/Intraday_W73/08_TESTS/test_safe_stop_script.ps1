$script = Get-Content (Join-Path $PSScriptRoot "..\11_DASHBOARD\stop_w73_dashboard.ps1") -Raw
if ($script -match '\$pid\b') {
    throw "Reserved PowerShell variable `$PID is still used as a variable."
}
if ($script -notmatch '\$targetPid') {
    throw "Expected targetPid safety variable not found."
}
Write-Host "SAFE_STOP_SCRIPT_STATIC_TEST=PASS"
