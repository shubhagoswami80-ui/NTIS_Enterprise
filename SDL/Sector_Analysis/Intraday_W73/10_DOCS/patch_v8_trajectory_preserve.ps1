# W73 V8 Feature Engine — controlled trajectory preservation patch
# Preconditions:
#   Current authoritative file SHA256 must match the frozen pre-patch hash.
#   Only the exact defective block is replaced.
# This patch preserves an explicitly supplied trajectory value when no
# price_observations are supplied. Missing values remain missing (None).
#
# Run from the user's existing PowerShell environment.

$Target = "E:\NSE_Daily_Analysis\SDL\Sector_Analysis\Intraday_W73\02_FEATURE_ENGINE\v8_feature_engine.py"
$ExpectedSha256 = "651F25632E6170EF6C86F6FCE667C026E317CA75A1FFB5AE17D43ECC74DF27DC"

if (-not (Test-Path -LiteralPath $Target)) {
    throw "TARGET_NOT_FOUND: $Target"
}

$ActualSha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToUpperInvariant()
if ($ActualSha256 -ne $ExpectedSha256) {
    throw "HASH_MISMATCH: expected $ExpectedSha256 but found $ActualSha256. No change made."
}

$Text = [System.IO.File]::ReadAllText($Target)

$Old = @'
        else:
            result["px_all_negative_pre_maturity"] = None
            result["px_negative_count_pre_maturity"] = None
            result["_trajectory_observations_used"] = 0
'@

$New = @'
        else:
            # Preserve an explicitly supplied point-in-time trajectory value.
            # Only fill from None when the caller did not provide the field.
            # Missing remains None; never coerce missing to False or zero.
            if "px_all_negative_pre_maturity" not in result:
                result["px_all_negative_pre_maturity"] = None
            if "px_negative_count_pre_maturity" not in result:
                result["px_negative_count_pre_maturity"] = None
            result["_trajectory_observations_used"] = 0
'@

$Count = ([regex]::Matches($Text, [regex]::Escape($Old))).Count
if ($Count -ne 1) {
    throw "PATCH_GUARD_FAILED: expected exactly 1 defective block, found $Count. No change made."
}

$Updated = $Text.Replace($Old, $New)
$Temp = "$Target.w73patch.tmp"
[System.IO.File]::WriteAllText($Temp, $Updated, [System.Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $Temp -Destination $Target -Force

$NewSha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToUpperInvariant()
Write-Output "STATUS COMPLETE"
Write-Output "TARGET=$Target"
Write-Output "OLD_SHA256=$ActualSha256"
Write-Output "NEW_SHA256=$NewSha256"
Write-Output "CHANGED_BLOCKS=1"
Write-Output "SEMANTICS=explicit_trajectory_preserved_missing_remains_none"
