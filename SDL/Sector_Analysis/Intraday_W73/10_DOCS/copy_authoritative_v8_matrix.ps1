$src = "E:\NSE_Daily_Analysis\SDL\Sector_Analysis\.sector_intelligence\maturity_conditional_pattern_discovery_v8\maturity_feature_matrix.csv"
$dst = "E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73\00_BASELINE\maturity_feature_matrix.csv"
if (-not (Test-Path -LiteralPath $src)) { throw "SOURCE NOT FOUND: $src" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
Copy-Item -LiteralPath $src -Destination $dst -Force
$hash = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
Write-Host "V8 MATRIX COPIED"
Write-Host "SOURCE=$src"
Write-Host "DESTINATION=$dst"
Write-Host "SHA256=$hash"
