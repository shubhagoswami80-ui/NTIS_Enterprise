# NTIS SDL - Start
# Starts ONLY the SDL production Streamlit app in the background.
# Port 8504. Uses actual port/process ownership for idempotent start.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8504
$App = Join-Path $ProjectRoot "app.py"

function Find-Python {
    $candidates = @(
        (Join-Path $ProjectRoot "..\.venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot "..\NTIS\.venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Working Python environment not found for SDL."
}

function Get-PortOwner {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($c) { return @($c | Select-Object -ExpandProperty OwningProcess -Unique) }
    return @()
}

$PythonExe = Find-Python
$RuntimeDir = Join-Path $ProjectRoot ".sdl_runtime"
$PidFile = Join-Path $RuntimeDir "sdl.pid"
$StdoutLog = Join-Path $RuntimeDir "sdl_stdout.log"
$StderrLog = Join-Path $RuntimeDir "sdl_stderr.log"

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

# If SDL already owns 8504, never launch a duplicate.
$owners = Get-PortOwner
if ($owners.Count -gt 0) {
    foreach ($ownerPid in $owners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine -and
            $proc.CommandLine -match "(?i)streamlit" -and
            $proc.CommandLine -match "(?i)\bapp\.py\b" -and
            $proc.CommandLine -match "(?i)--server\.port(?:=|\s+)8504") {
            Set-Content -Path $PidFile -Value $ownerPid -Encoding ASCII
            Write-Host "SDL is already running. PID: $ownerPid"
            Write-Host "Open: http://localhost:$Port"
            exit 0
        }
    }
    Write-Error "Port $Port is occupied by a process that is not identified as SDL. No new SDL instance was started."
    exit 1
}

Remove-Item $StdoutLog,$StderrLog -Force -ErrorAction SilentlyContinue

$p = Start-Process `
    -FilePath $PythonExe `
    -WorkingDirectory $ProjectRoot `
    -ArgumentList @("-m","streamlit","run",$App,"--server.port",$Port.ToString(),"--server.headless","true") `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError $StderrLog `
    -PassThru

Set-Content -Path $PidFile -Value $p.Id -Encoding ASCII

Start-Sleep -Seconds 3
$owners = Get-PortOwner

if ($owners.Count -eq 0) {
    Write-Error "SDL did not bind to port $Port. Check $StderrLog"
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

$matched = $false
foreach ($ownerPid in $owners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -and
        $proc.CommandLine -match "(?i)streamlit" -and
        $proc.CommandLine -match "(?i)\bapp\.py\b" -and
        $proc.CommandLine -match "(?i)--server\.port(?:=|\s+)8504") {
        Set-Content -Path $PidFile -Value $ownerPid -Encoding ASCII
        $matched = $true
        break
    }
}

if (-not $matched) {
    Write-Error "Port $Port is listening, but ownership could not be verified as SDL. Refusing to continue."
    exit 1
}

Write-Host "SDL started in background."
Write-Host "SDL PID: $((Get-Content $PidFile | Select-Object -First 1))"
Write-Host "Open: http://localhost:$Port"
Write-Host "Stdout: $StdoutLog"
Write-Host "Stderr: $StderrLog"
