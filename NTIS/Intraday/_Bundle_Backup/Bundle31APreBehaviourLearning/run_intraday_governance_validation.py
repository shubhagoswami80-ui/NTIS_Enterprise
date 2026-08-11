from pathlib import Path

print("="*60)
print("NTIS INTRADAY GOVERNANCE VALIDATION")
print("="*60)

files = [
"intraday_data_quality_monitor.py",
"intraday_duplicate_detector.py",
"intraday_junk_data_analyzer.py",
"intraday_archive_manager.py",
"intraday_storage_monitor.py",
"run_intraday_governance_validation.py"
]

ok = True

for f in files:
    status = Path(f).exists()
    print(f"{f:<45}", "PASS" if status else "FAIL")
    ok = ok and status

print("="*60)
print(
    "GOVERNANCE FOUNDATION READY"
    if ok
    else "GOVERNANCE FOUNDATION INCOMPLETE"
)
print("="*60)
