$Root="E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73"
$BundleRoot=(Split-Path -Parent $MyInvocation.MyCommand.Path)
$Files=@(
@("03_LIVE_ADAPTER\w73_source_adapter.py","03_LIVE_ADAPTER\w73_source_adapter.py"),
@("04_REPLAY\w73_replay_engine.py","04_REPLAY\w73_replay_engine.py"),
@("05_HISTORICAL\README.md","05_HISTORICAL\README.md"),
@("08_TESTS\test_w73_source_adapter.py","08_TESTS\test_w73_source_adapter.py"),
@("10_DOCS\W73_SOURCE_CONTRACT.md","10_DOCS\W73_SOURCE_CONTRACT.md"),
@("10_DOCS\W73_REPLAY_CONTRACT.md","10_DOCS\W73_REPLAY_CONTRACT.md")
)
foreach($pair in $Files){
  $src=Join-Path $BundleRoot $pair[0]
  $dst=Join-Path $Root $pair[1]
  if(Test-Path -LiteralPath $dst){throw "DESTINATION_ALREADY_EXISTS: $dst. No overwrite performed."}
  Copy-Item -LiteralPath $src -Destination $dst
}
Write-Output "STATUS COMPLETE"
Write-Output "FILES_COPIED=$($Files.Count)"
Write-Output "EXTERNAL_SOURCE_READ_ONLY=D:\My-data\Share_P&L\Ichart Data\Screenshot"
