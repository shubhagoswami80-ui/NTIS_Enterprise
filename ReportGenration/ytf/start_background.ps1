# Start ONLY the ytf collector.
$ErrorActionPreference = "Stop"

$ProjectRoot = "E:\NSE_Daily_Analysis\ReportGenration\ytf"
$ScriptPath  = Join-Path $ProjectRoot "ftd.py"

# The confirmed shared virtual environment used on this system.
$PythonPath  = "E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"

$RuntimeDir  = Join-Path $ProjectRoot "runtime_control"
$PidFile     = Join-Path $RuntimeDir "ftd.pid"
$OutLog      = Join-Path $RuntimeDir "ftd_stdout.log"
$ErrLog      = Join-Path $RuntimeDir "ftd_stderr.log"

if (!(Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Target script not found: $ScriptPath"
}
if (!(Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python executable not found: $PythonPath"
}

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

# Do not start a second copy if the recorded target process is still alive.
if (Test-Path -LiteralPath $PidFile) {
    $pidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    [int]$existingPid = 0
    if ([int]::TryParse($pidText, [ref]$existingPid) -and $existingPid -gt 0) {
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $existingPid" -ErrorAction SilentlyContinue
        if ($existing) {
            $cmd = [string]$existing.CommandLine
            if ($cmd -like "*$ScriptPath*") {
                Write-Host "ytf collector is already running. PID: $existingPid"
                exit 0
            }
            throw "PID file points to an unrelated process. Nothing started."
        }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

$process = Start-Process `
    -FilePath $PythonPath `
    -ArgumentList @("-u", $ScriptPath) `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ASCII

Start-Sleep -Milliseconds 800
$started = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction SilentlyContinue
if (!$started) {
    Write-Host "Collector exited immediately. Review:"
    Write-Host $ErrLog
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "Started ONLY ytf collector."
Write-Host "PID: $($process.Id)"
Write-Host "Python: $PythonPath"
Write-Host "Script: $ScriptPath"
Write-Host "PID file: $PidFile"
