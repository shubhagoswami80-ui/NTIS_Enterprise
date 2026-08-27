# NTIS SDL Preview - Start
# Starts ONLY the isolated SDL preview Streamlit app in the background.
# Port 8587.

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
    foreach ($p in $candidates) {
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Working Python environment not found for SDL preview."
}

function Get-PortOwners {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($c) { return @($c | Select-Object -ExpandProperty OwningProcess -Unique) }
    return @()
}

$Python = Find-Python
$Runtime = Join-Path $AppDir ".sdl_preview_runtime"
$PidFile = Join-Path $Runtime "sdl_preview.pid"
$Stdout = Join-Path $Runtime "sdl_preview_stdout.log"
$Stderr = Join-Path $Runtime "sdl_preview_stderr.log"

New-Item -ItemType Directory -Path $Runtime -Force | Out-Null

$owners = Get-PortOwners
if ($owners.Count -gt 0) {
    foreach ($ownerPid in $owners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine -and
            $proc.CommandLine -match "(?i)sdl_decision_centre_preview\.py" -and
            $proc.CommandLine -match "(?i)streamlit" -and
            $proc.CommandLine -match "(?i)--server\.port(?:=|\s+)8587") {
            Set-Content -Path $PidFile -Value $ownerPid -Encoding ASCII
            Write-Host "SDL preview is already running. PID: $ownerPid"
            Write-Host "Open: http://localhost:$Port"
            exit 0
        }
    }
    Write-Error "Port $Port is occupied by a process that is not identified as SDL preview. No new preview was started."
    exit 1
}

Remove-Item $Stdout,$Stderr -Force -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $Python -WorkingDirectory $AppDir `
    -ArgumentList @("-m","streamlit","run",$App,"--server.port",$Port.ToString(),"--server.headless","true") `
    -WindowStyle Hidden -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru

Set-Content $PidFile $p.Id -Encoding ASCII
Start-Sleep -Seconds 3

$owners = Get-PortOwners
if ($owners.Count -eq 0) {
    Write-Error "SDL preview did not bind to port $Port. Check $Stderr"
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

$matched = $false
foreach ($ownerPid in $owners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -and
        $proc.CommandLine -match "(?i)sdl_decision_centre_preview\.py" -and
        $proc.CommandLine -match "(?i)streamlit" -and
        $proc.CommandLine -match "(?i)--server\.port(?:=|\s+)8587") {
        Set-Content $PidFile $ownerPid -Encoding ASCII
        $matched = $true
        break
    }
}

if (-not $matched) {
    Write-Error "Port $Port is listening, but ownership could not be verified as SDL preview. Refusing to continue."
    exit 1
}

Write-Host "SDL professional preview started in background."
Write-Host "PID: $((Get-Content $PidFile | Select-Object -First 1))"
Write-Host "Open: http://localhost:$Port"
