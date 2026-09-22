$Root="E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73"
$BundleRoot=(Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Files=@(
@("11_DASHBOARD\w73_dashboard.py","11_DASHBOARD\w73_dashboard.py"),
@("11_DASHBOARD\start_w73_dashboard.ps1","11_DASHBOARD\start_w73_dashboard.ps1"),
@("12_INTEGRATION\w73_entrypoint.py","12_INTEGRATION\w73_entrypoint.py"),
@("12_INTEGRATION\README.md","12_INTEGRATION\README.md"),
@("08_TESTS\test_w73_entrypoint.py","08_TESTS\test_w73_entrypoint.py"),
@("08_TESTS\test_w73_dashboard_structure.py","08_TESTS\test_w73_dashboard_structure.py"),
@("10_DOCS\W73_DASHBOARD_ARCHITECTURE_V1.md","10_DOCS\W73_DASHBOARD_ARCHITECTURE_V1.md"),
@("10_DOCS\W73_SEMANTIC_PARITY_IMPLEMENTATION_GATE.md","10_DOCS\W73_SEMANTIC_PARITY_IMPLEMENTATION_GATE.md")
)
$Copied=0;$Skipped=0
foreach($pair in $Files){
  $src=Join-Path $BundleRoot $pair[0];$dst=Join-Path $Root $pair[1]
  if(-not(Test-Path -LiteralPath $src)){throw "BUNDLE_SOURCE_MISSING: $src"}
  if(Test-Path -LiteralPath $dst){Write-Output "SKIP_EXISTS=$dst";$Skipped++;continue}
  Copy-Item -LiteralPath $src -Destination $dst
  Write-Output "COPIED=$dst";$Copied++
}
Write-Output "STATUS COMPLETE";Write-Output "COPIED=$Copied";Write-Output "SKIPPED_EXISTING=$Skipped";Write-Output "EXTERNAL_SOURCE=READ_ONLY"
