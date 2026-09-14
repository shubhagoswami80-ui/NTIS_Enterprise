param(
    [string]$TradeDate = "",
    [string]$Config = "E:\NSE_Daily_Analysis\ReportGenration\ytf\NSE\nse_config.json"
)

$Python = "E:\NSE_Daily_Analysis\NTIS\.venv\Scripts\python.exe"
$Runner = "E:\NSE_Daily_Analysis\ReportGenration\ytf\NSE\nse_configured_runner.py"

$argsList = @($Runner, "--config", $Config, "--write-manifest")
if ($TradeDate -ne "") {
    $argsList += @("--trade-date", $TradeDate)
}

& $Python @argsList
exit $LASTEXITCODE
