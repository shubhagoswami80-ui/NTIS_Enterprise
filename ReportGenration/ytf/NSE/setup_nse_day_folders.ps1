param(
    [string]$TradeDate = ""
)

$feedRoot = "D:\My-data\Share_P&L\ytdata\nse_feed"

if ([string]::IsNullOrWhiteSpace($TradeDate)) {
    $dt = Get-Date
} else {
    $dt = [datetime]::ParseExact($TradeDate, "yyyy-MM-dd", $null)
}

$year = $dt.ToString("yyyy")
$month = $dt.ToString("MMMM")
$day = $dt.ToString("yyyy-MM-dd")

$dayRoot = Join-Path $feedRoot "$year\$month\$day"
$rawRoot = $dayRoot
$outputRoot = Join-Path $dayRoot "output"

New-Item -ItemType Directory -Path $rawRoot -Force | Out-Null
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

Write-Host "NSE raw folder:    $rawRoot"
Write-Host "NSE output folder: $outputRoot"
