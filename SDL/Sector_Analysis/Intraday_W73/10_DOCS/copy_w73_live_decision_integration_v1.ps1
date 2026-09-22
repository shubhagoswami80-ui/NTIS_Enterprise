$ErrorActionPreference="Stop"
$SourceRoot=Split-Path -Parent $PSScriptRoot
$W73Root="E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73"
$files=@(
    "06_ALERTS\w73_live_decision_service.py",
    "07_OUTPUT\live_decision_contract_v2.json",
    "08_TESTS\test_w73_live_decision_service.py",
    "08_TESTS\test_w73_dashboard_integration.py",
    "10_DOCS\LIVE_DECISION_INTEGRATION_V1.md",
    "10_DOCS\DEPLOYMENT_INSTRUCTIONS_V2.md"
)
foreach($rel in $files){
    $src=Join-Path $SourceRoot $rel
    $dst=Join-Path $W73Root $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
Copy-Item -LiteralPath (Join-Path $SourceRoot "11_DASHBOARD\w73_dashboard.py") -Destination (Join-Path $W73Root "11_DASHBOARD\w73_dashboard.py") -Force
Copy-Item -LiteralPath (Join-Path $SourceRoot "11_DASHBOARD\start_w73_dashboard.ps1") -Destination (Join-Path $W73Root "11_DASHBOARD\start_w73_dashboard.ps1") -Force
Write-Output "W73_LIVE_DECISION_INTEGRATION_COPIED"
