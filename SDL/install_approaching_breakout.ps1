$ErrorActionPreference = "Stop"

$root = "E:\NSE_Daily_Analysis\SDL"
Set-Location $root

$module = Join-Path $root "approaching_breakout.py"
$app = Join-Path $root "app.py"

Write-Host "Installing SDL 50% Approaching Breakout layer..."

# ---------------------------------------------------------------------------
# The module is supplied in this deployment bundle.
# ---------------------------------------------------------------------------
if (-not (Test-Path $module)) {
    throw "approaching_breakout.py was not found in SDL root."
}

# ---------------------------------------------------------------------------
# Existing pipeline integration is intentionally preserved.
# The earlier installation already calls:
#     save_approaching_breakouts(...)
# and imports the module.
# ---------------------------------------------------------------------------
$pipeline = Join-Path $root "pipeline.py"
if (-not (Test-Path $pipeline)) {
    throw "pipeline.py not found."
}

$p = Get-Content $pipeline -Raw
if ($p -notmatch 'from approaching_breakout import save_approaching_breakouts') {
    $anchor = "from storage import ("
    if (-not $p.Contains($anchor)) {
        throw "pipeline.py integration anchor not found."
    }

    $p = $p.Replace(
        $anchor,
        "from approaching_breakout import save_approaching_breakouts`r`n`r`n" + $anchor
    )
}

if ($p -notmatch 'save_approaching_breakouts\(') {
    $anchor = @'
    df = _apply_frozen_base(
        df,
        base_map,
    )

'@

    if (-not $p.Contains($anchor)) {
        throw "pipeline.py frozen-base anchor not found."
    }

    $call = @'
    # ------------------------------------------------------------------
    # SDL 50% Approaching Breakout layer.
    #
    # Additive only. Existing STD-Intraday Breakout event logic is
    # untouched.
    # ------------------------------------------------------------------
    save_approaching_breakouts(
        df,
        trading_date,
        observed_at,
        Path(EVENT_CSV).parent / "approaching_breakouts.csv",
    )

'@

    $p = $p.Replace($anchor, $anchor + $call)
}

[IO.File]::WriteAllText(
    $pipeline,
    $p,
    (New-Object System.Text.UTF8Encoding($false))
)

# ---------------------------------------------------------------------------
# Correct dashboard wording so 100% breakout stocks are NOT excluded from
# the 50%-reached layer.
# ---------------------------------------------------------------------------
if (Test-Path $app) {
    $a = Get-Content $app -Raw

    $old = "Stocks at or above 50% of their own frozen opening straddle and still below the exact 1× breakout level."
    $new = "Stocks that have reached at least 50% of their own frozen opening straddle. Reaching 100% does not remove them from this list."

    if ($a.Contains($old)) {
        $a = $a.Replace($old, $new)
    }

    $old2 = "No stocks are currently approaching the frozen straddle breakout."
    $new2 = "No stocks have reached the 50% frozen-straddle level for the latest processed trading day."

    if ($a.Contains($old2)) {
        $a = $a.Replace($old2, $new2)
    }

    [IO.File]::WriteAllText(
        $app,
        $a,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
python -c "import approaching_breakout; print('APPROACHING MODULE IMPORT: PASS')"
python -c "from pathlib import Path; import pipeline; print('PIPELINE IMPORT: PASS'); print('APPROACHING CSV:', Path(pipeline.EVENT_CSV).parent / 'approaching_breakouts.csv')"

Write-Host ""
Write-Host "SDL 50% APPROACHING BREAKOUT LAYER INSTALLED"
Write-Host "Existing SDL STD-Intraday Breakout ledger: UNCHANGED"
Write-Host "Approaching persistence: approaching_breakouts.csv"
Write-Host "Rule: first observed >=50% per (trading_date, symbol)"
Write-Host "100% breakout status does NOT disqualify a 50% record"
