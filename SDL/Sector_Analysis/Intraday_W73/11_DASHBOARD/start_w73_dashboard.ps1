$ErrorActionPreference="Stop"

$W73Root="E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73"
$App=Join-Path $W73Root "11_DASHBOARD\w73_dashboard.py"
$PidDir=Join-Path $W73Root "11_DASHBOARD\.runtime"
$PidFile=Join-Path $PidDir "w73_dashboard.pid.json"
$Port=9005

New-Item -ItemType Directory -Force -Path $PidDir | Out-Null

if(Test-Path -LiteralPath $PidFile){
    try{
        $old=Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
        $p=Get-Process -Id ([int]$old.pid) -ErrorAction SilentlyContinue
        if($p){
            Write-Output "W73_ALREADY_RUNNING_PID=$($p.Id)"
            Write-Output "W73_PORT=$Port"
            exit 0
        }
        Remove-Item -LiteralPath $PidFile -Force
    } catch {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
}

$python=(Get-Command python -ErrorAction Stop).Source
$args=@(
    "-m","streamlit","run",$App,
    "--server.port",$Port,
    "--server.headless","true",
    "--browser.gatherUsageStats","false"
)

$p=Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $W73Root -PassThru

Start-Sleep -Milliseconds 800

$record=[ordered]@{
    pid=$p.Id
    python=$python
    app=$App
    port=$Port
    started_at=(Get-Date).ToString("o")
    command="python -m streamlit run `"$App`" --server.port $Port --server.headless true --browser.gatherUsageStats false"
}
$record | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding UTF8

Write-Output "W73_STARTED"
Write-Output "PID=$($p.Id)"
Write-Output "PORT=$Port"
Write-Output "APP=$App"
Write-Output "PID_FILE=$PidFile"
