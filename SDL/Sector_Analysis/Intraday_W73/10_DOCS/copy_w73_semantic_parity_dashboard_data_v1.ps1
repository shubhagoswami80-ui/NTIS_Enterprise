$Root="E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73"
$BundleRoot=(Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Files=@(
@("02_FEATURE_ENGINE\w73_v8_semantic_parity.py","02_FEATURE_ENGINE\w73_v8_semantic_parity.py"),
@("07_OUTPUT\w73_dashboard_data_contract.json","07_OUTPUT\w73_dashboard_data_contract.json"),
@("08_TESTS\test_w73_semantic_parity_structure.py","08_TESTS\test_w73_semantic_parity_structure.py"),
@("10_DOCS\W73_SEMANTIC_PARITY_DASHBOARD_DATA_V1.md","10_DOCS\W73_SEMANTIC_PARITY_DASHBOARD_DATA_V1.md")
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
