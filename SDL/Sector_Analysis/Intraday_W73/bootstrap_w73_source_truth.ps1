
$ErrorActionPreference = "Stop"

$W73 = "E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73"
$Old = "E:\NSE_Daily_Analysis\SDL\Sector_Analysis"
$Intel = Join-Path $Old ".sector_intelligence"

New-Item -ItemType Directory -Force -Path $W73 | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "00_BASELINE") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "01_RESEARCH_SOURCE") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "02_FEATURE_ENGINE") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "03_LIVE_ADAPTER") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "04_REPLAY") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "05_HISTORICAL") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "06_ALERTS") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "07_OUTPUT") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "08_TESTS") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "09_ARCHIVE") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $W73 "10_DOCS") | Out-Null

$copies = @(
    @{Src=(Join-Path $Intel "v12_6_exhaustive_research\chronological_validation_corrected.csv"); Dst="00_BASELINE\chronological_validation_corrected.csv"},
    @{Src=(Join-Path $Old "maturity_conditional_pattern_discovery_v8.py"); Dst="01_RESEARCH_SOURCE\maturity_conditional_pattern_discovery_v8.py"},
    @{Src=(Join-Path $Old "v12_5_exact_v8_component_stability.py"); Dst="01_RESEARCH_SOURCE\v12_5_exact_v8_component_stability.py"},
    @{Src=(Join-Path $Old "v12_6_exhaustive_pattern_miner.py"); Dst="01_RESEARCH_SOURCE\v12_6_exhaustive_pattern_miner.py"},
    @{Src=(Join-Path $Old "v12_6_phase3a_corrected_validation.py"); Dst="01_RESEARCH_SOURCE\v12_6_phase3a_corrected_validation.py"},
    @{Src=(Join-Path $Old "data_strength_combination_study.py"); Dst="01_RESEARCH_SOURCE\data_strength_combination_study.py"},
    @{Src=(Join-Path $Old "smart_replay_strategy_study.py"); Dst="01_RESEARCH_SOURCE\smart_replay_strategy_study.py"}
)

$manifest = @()
foreach ($item in $copies) {
    if (Test-Path -LiteralPath $item.Src -PathType Leaf) {
        $dst = Join-Path $W73 $item.Dst
        Copy-Item -LiteralPath $item.Src -Destination $dst -Force
        $srcHash = (Get-FileHash -LiteralPath $item.Src -Algorithm SHA256).Hash
        $dstHash = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
        $manifest += [pscustomobject]@{
            Source=$item.Src
            Destination=$dst
            SourceSHA256=$srcHash
            DestinationSHA256=$dstHash
            Match=($srcHash -eq $dstHash)
        }
    } else {
        $manifest += [pscustomobject]@{
            Source=$item.Src
            Destination=(Join-Path $W73 $item.Dst)
            SourceSHA256=""
            DestinationSHA256=""
            Match=$false
        }
    }
}

$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $W73 "10_DOCS\migration_manifest.json") -Encoding UTF8

$required = @(
    (Join-Path $W73 "00_BASELINE\chronological_validation_corrected.csv"),
    (Join-Path $W73 "01_RESEARCH_SOURCE\maturity_conditional_pattern_discovery_v8.py"),
    (Join-Path $W73 "01_RESEARCH_SOURCE\v12_5_exact_v8_component_stability.py"),
    (Join-Path $W73 "01_RESEARCH_SOURCE\v12_6_exhaustive_pattern_miner.py"),
    (Join-Path $W73 "01_RESEARCH_SOURCE\v12_6_phase3a_corrected_validation.py")
)

$missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })

Write-Host "W73 SOURCE-OF-TRUTH MIGRATION COMPLETE"
Write-Host "ROOT=$W73"
Write-Host "COPIED=$(@($manifest | Where-Object Match).Count)"
Write-Host "MISSING=$($missing.Count)"
if ($missing.Count -gt 0) {
    Write-Host "MISSING_FILES:"
    $missing | ForEach-Object { Write-Host $_ }
}
Write-Host "MANIFEST=$(Join-Path $W73 '10_DOCS\migration_manifest.json')"
