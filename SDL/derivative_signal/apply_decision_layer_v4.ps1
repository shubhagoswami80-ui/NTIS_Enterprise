$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$dashboard = Join-Path $root "dashboard.py"
$adapter = Join-Path $root "multi_source_adapter.py"
$evidence = Join-Path $root "decision_evidence.py"

foreach ($p in @($dashboard,$adapter,$evidence)) {
    if (-not (Test-Path $p)) { throw "Required file not found: $p" }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item $dashboard "$dashboard.before_decision_layer_v4_$stamp.bak" -Force
Copy-Item $adapter "$adapter.before_decision_layer_v4_$stamp.bak" -Force

$d = Get-Content $dashboard -Raw

if ($d -notmatch '(?m)^\s*from decision_evidence import') {
    $needle = 'from derivative_signal.signal_engine import build_signal'
    if ($d -notmatch [regex]::Escape($needle)) {
        throw "dashboard.py: signal_engine import anchor not found."
    }
    $d = $d.Replace($needle, $needle + "`r`nfrom decision_evidence import enrich_decision, merge_evidence")
}

$procMatch = [regex]::Match($d, '(?s)def _process_snapshot\(\s*.*?(?=\r?\ndef process_selected_source)')
if (-not $procMatch.Success) {
    throw "dashboard.py: _process_snapshot function boundary not found."
}
if ($procMatch.Value -notmatch 'merge_evidence') {
    $replacement = @'
def _process_snapshot(
    path: Path,
    trading_date: str,
    previous: dict[str, dict],
) -> pd.DataFrame:
    # Process the selected BASE snapshot using all evidence files discovered
    # from the same dashboard-selected source folder.
    merged, _meta = merge_evidence(path, trading_date)
    rows = []
    for record in merged.to_dict(orient="records"):
        symbol = str(record.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        signal = build_signal(record, previous.get(symbol))
        signal = enrich_decision(signal, record)
        rows.append(signal)
    return pd.DataFrame(rows)

'@
    $d = $d.Substring(0, $procMatch.Index) + $replacement + $d.Substring($procMatch.Index + $procMatch.Length)
    Write-Host "dashboard.py: _process_snapshot updated."
} else {
    Write-Host "dashboard.py: _process_snapshot already uses decision evidence; preserved."
}

$strengthMatch = [regex]::Match($d, '(?s)def _strength_html\([^\r\n]*\).*?(?=\r?\ndef )')
if ($strengthMatch.Success) {
    if ($strengthMatch.Value -notmatch 'direction\s*:\s*str') {
        $replacement = @'
def _strength_html(score: int, direction: str = "NEUTRAL") -> str:
    score = max(0, min(5, int(score or 0)))
    direction = str(direction or "NEUTRAL").upper()
    circles = []
    for index in range(1, 6):
        if index <= score:
            if direction == "BEARISH":
                cls = "filled-red"
            elif direction == "BULLISH":
                cls = "filled-green"
            elif score >= 3:
                cls = "filled-amber"
            else:
                cls = "filled-grey"
        else:
            cls = "empty"
        circles.append(f'<span class="strength-circle {cls}"></span>')
    return "".join(circles)

'@
        $d = $d.Substring(0, $strengthMatch.Index) + $replacement + $d.Substring($strengthMatch.Index + $strengthMatch.Length)
        Write-Host "dashboard.py: strength helper made direction-aware."
    } else {
        Write-Host "dashboard.py: strength helper already direction-aware; preserved."
    }
    $callOld = "_strength_html(int(row.get('strength', 0) or 0))"
    $callNew = "_strength_html(int(row.get('strength', 0) or 0), row.get('direction', 'NEUTRAL'))"
    if ($d.Contains($callOld)) {
        $d = $d.Replace($callOld, $callNew)
        Write-Host "dashboard.py: strength call updated."
    }
    if ($d -notmatch '(?s)\.filled-red\s*\{') {
        $greenMatch = [regex]::Match($d, '(?s)\.filled-green\s*\{\s*background:\s*#16a34a;\s*border-color:\s*#16a34a;\s*\}')
        if ($greenMatch.Success) {
            $redCss = $greenMatch.Value + @'

        .filled-red {
            background: #dc2626;
            border-color: #dc2626;
        }
'@
            $d = $d.Substring(0, $greenMatch.Index) + $redCss + $d.Substring($greenMatch.Index + $greenMatch.Length)
            Write-Host "dashboard.py: red strength CSS added."
        }
    }
} else {
    Write-Host "dashboard.py: _strength_html helper not present; strength rendering preserved."
}

Set-Content -Path $dashboard -Value $d -Encoding UTF8

$a = Get-Content $adapter -Raw
if ($a -match 'merged\[f"_source_\{role\}"\]\s*=\s*True') {
    $a = [regex]::Replace($a, 'merged\[f"_source_\{role\}"\]\s*=\s*True', 'merged[f"_source_{role}"] = merged["symbol"].isin(lookup.index)', 1)
    Write-Host "multi_source_adapter.py: source-family presence made symbol-specific."
} else {
    Write-Host "multi_source_adapter.py: source-family presence already symbol-specific; preserved."
}

$fallback = '(?s)\s*# Futures can also be supplied by the Support/Resistance reports\.\s*if "FUTURES" not in b\.files.*?\s*b\.files\["FUTURES"\]\s*=\s*b\.files\.get\("SUPPORT"\)\s*or\s*b\.files\.get\("RESISTANCE"\)'
if ($a -match $fallback) {
    $a = [regex]::Replace($a, $fallback, "", 1)
    Write-Host "multi_source_adapter.py: unsafe S/R-to-FUTURES fallback removed."
}

Set-Content -Path $adapter -Value $a -Encoding UTF8

Write-Host ""
Write-Host "Decision Layer v4 applied successfully."
Write-Host "Dashboard: $dashboard"
Write-Host "Adapter: $adapter"
Write-Host "Evidence: $evidence"
Write-Host "Root SDL\source_loader.py was NOT modified."
Write-Host "SDL\sdl_Backup was NOT modified."
Write-Host "Git was NOT modified."
