$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8587
$App = Join-Path $AppDir "sdl_decision_centre_preview.py"

function Find-Python {
    $candidates = @(
        (Join-Path $AppDir "..\.venv\Scripts\python.exe"),
        (Join-Path $AppDir "..\NTIS\.venv\Scripts\python.exe"),
        (Join-Path $AppDir ".venv\Scripts\python.exe")
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return (Resolve-Path $p).Path } }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Working Python environment not found for SDL preview."
}
$Python = Find-Python
$Runtime = Join-Path $AppDir ".sdl_preview_runtime"
$PidFile = Join-Path $Runtime "sdl_preview.pid"
$Stdout = Join-Path $Runtime "sdl_preview_stdout.log"
$Stderr = Join-Path $Runtime "sdl_preview_stderr.log"
New-Item -ItemType Directory -Path $Runtime -Force | Out-Null

$existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*sdl_decision_centre_preview.py*" -and $_.CommandLine -like "*--server.port $Port*" } |
    Select-Object -First 1
if ($existing) {
    Set-Content $PidFile $existing.ProcessId -Encoding ASCII
    Write-Host "SDL preview is already running on port $Port."
    Write-Host "Open: http://localhost:$Port"
    exit 0
}
Remove-Item $Stdout,$Stderr -Force -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath $Python -WorkingDirectory $AppDir `
    -ArgumentList @("-m","streamlit","run",$App,"--server.port",$Port.ToString(),"--server.headless","true") `
    -WindowStyle Hidden -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru
Set-Content $PidFile $proc.Id -Encoding ASCII
Start-Sleep -Seconds 3
if (-not (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue)) {
    Write-Error "SDL preview exited during startup. Check $Stderr"
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "SDL professional preview started in background."
Write-Host "PID: $($proc.Id)"
Write-Host "Open: http://localhost:$Port"
