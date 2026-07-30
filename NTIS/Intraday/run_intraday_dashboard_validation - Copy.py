from pathlib import Path

print("="*60)
print("NTIS INTRADAY DASHBOARD VALIDATION")
print("="*60)

files = [
"intraday_dashboard.py",
"intraday_dashboard_data_loader.py",
"intraday_dashboard_health_panel.py",
"intraday_dashboard_snapshot_viewer.py",
"intraday_dashboard_compare_engine.py",
"run_intraday_dashboard_validation.py"
]

ok=True

for f in files:
    status=Path(f).exists()
    print(f"{f:<45}", "PASS" if status else "FAIL")
    ok = ok and status

print("="*60)

print(
    "DASHBOARD FOUNDATION READY"
    if ok
    else "DASHBOARD FOUNDATION INCOMPLETE"
)

print("="*60)
