$Root="E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73"
$BundleRoot=(Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Files=@(
@("02_FEATURE_ENGINE\w73_raw_v8_bridge.py","02_FEATURE_ENGINE\w73_raw_v8_bridge.py"),
@("04_REPLAY\w73_point_in_time_replay.py","04_REPLAY\w73_point_in_time_replay.py"),
@("05_HISTORICAL\w73_replay_manifest.py","05_HISTORICAL\w73_replay_manifest.py"),
@("06_ALERTS\w73_alert_gate.py","06_ALERTS\w73_alert_gate.py"),
@("08_TESTS\test_w73_finishline_bundle.py","08_TESTS\test_w73_finishline_bundle.py"),
@("08_TESTS\test_w73_replay_leakage.py","08_TESTS\test_w73_replay_leakage.py"),
@("10_DOCS\W73_FINISHLINE_BUNDLE_V1.md","10_DOCS\W73_FINISHLINE_BUNDLE_V1.md"),
@("10_DOCS\W73_SEMANTIC_PARITY_GATE.md","10_DOCS\W73_SEMANTIC_PARITY_GATE.md"),
@("10_DOCS\run_finishline_validation.ps1","10_DOCS\run_finishline_validation.ps1")
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
