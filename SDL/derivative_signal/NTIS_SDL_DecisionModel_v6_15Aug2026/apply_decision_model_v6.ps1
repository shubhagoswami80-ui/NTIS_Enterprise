$ErrorActionPreference='Stop'
$Bundle=Split-Path -Parent $MyInvocation.MyCommand.Path
$Target=Resolve-Path (Join-Path $Bundle '..')
$D=Join-Path $Target 'dashboard.py'; $E=Join-Path $Target 'decision_evidence.py'
if(!(Test-Path $D) -or !(Test-Path $E)){throw "SAFE STOP: derivative_signal files not found in $Target"}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'; $backup=Join-Path $Target ".decision_model_v6_backup_$stamp"
New-Item -ItemType Directory -Path $backup -Force|Out-Null
Copy-Item $D (Join-Path $backup 'dashboard.py') -Force; Copy-Item $E (Join-Path $backup 'decision_evidence.py') -Force
python (Join-Path $Bundle 'apply_decision_model_v6.py')
if($LASTEXITCODE -ne 0){throw "Patch failed. Backup: $backup"}
python -m py_compile $D $E
if($LASTEXITCODE -ne 0){throw "Validation failed. Backup: $backup"}
Write-Host 'FINAL DECISION MODEL v6 APPLIED AND VALIDATED'
Write-Host 'Hard +/-0.75% eligibility gate preserved.'
Write-Host 'Evidence-weighted 0-100 score added.'
Write-Host 'Decision strength added.'
Write-Host 'S/R and first-range fields are available to the score when supplied.'
Write-Host 'signal_engine.py unchanged.'
Write-Host 'SDL data/state untouched.'
Write-Host "Backup: $backup"
