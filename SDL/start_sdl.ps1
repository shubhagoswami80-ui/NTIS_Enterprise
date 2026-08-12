# NTIS SDL - Start
# Starts ONLY the SDL Streamlit process in the background.
# SDL is assigned port 8504.

$ProjectRoot = "E:\NSE_Daily_Analysis\SDL"
$PythonExe   = "E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"
$Port        = 8504
$RuntimeDir  = Join-Path $ProjectRoot ".sdl_runtime"
$PidFile     = Join-Path $RuntimeDir "sdl.pid"
$StdoutLog   = Join-Path $RuntimeDir "sdl_stdout.log"
$StderrLog   = Join-Path $RuntimeDir "sdl_stderr.log"

if (-not (Test-Path $PythonExe)) {
    Write-Error "NTIS Python not found: $PythonExe"
    exit 1
}

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

if (Test-Path $PidFile) {
    $savedPid = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($savedPid -match '^\d+$') {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$savedPid" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine -and
            $proc.CommandLine -like "*$ProjectRoot*" -and
            $proc.CommandLine -like "*streamlit*" -and
            $proc.CommandLine -like "*app.py*" -and
            $proc.CommandLine -like "*--server.port $Port*") {
            Write-Host "SDL is already running. PID: $savedPid"
            Write-Host "Open: http://localhost:$Port"
            exit 0
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

$existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -like "*$ProjectRoot*" -and
        $_.CommandLine -like "*streamlit*" -and
        $_.CommandLine -like "*app.py*" -and
        $_.CommandLine -like "*--server.port $Port*"
    } |
    Select-Object -First 1

if ($existing) {
    Set-Content -Path $PidFile -Value $existing.ProcessId -Encoding ASCII
    Write-Host "SDL is already running. PID: $($existing.ProcessId)"
    Write-Host "Open: http://localhost:$Port"
    exit 0
}

Remove-Item $StdoutLog -Force -ErrorAction SilentlyContinue
Remove-Item $StderrLog -Force -ErrorAction SilentlyContinue

$p = Start-Process `
    -FilePath $PythonExe `
    -WorkingDirectory $ProjectRoot `
    -ArgumentList @("-m","streamlit","run","app.py","--server.port",$Port.ToString(),"--server.headless","true") `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError $StderrLog `
    -PassThru

Set-Content -Path $PidFile -Value $p.Id -Encoding ASCII

Start-Sleep -Seconds 3

$check = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue

if (-not $check) {
    Write-Error "SDL exited during startup. Check: $StdoutLog and $StderrLog"
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "SDL started in background."
Write-Host "SDL PID: $($p.Id)"
Write-Host "Open: http://localhost:$Port"
Write-Host "Stdout: $StdoutLog"
Write-Host "Stderr: $StderrLog"
