from pathlib import Path

print("=" * 60)
print("NTIS INTRADAY DASHBOARD VALIDATION")
print("=" * 60)

dashboard_core = [
    "intraday_dashboard.py",
    "intraday_latest_snapshot_resolver.py",
]

dashboard_components = [
    "intraday_dashboard_health_panel.py",
    "intraday_dashboard_snapshot_viewer.py",
    "intraday_dashboard_compare_engine.py",
]

validation_files = [
    "run_intraday_dashboard_validation.py",
]

overall_status = True


def validate_group(title, files):
    global overall_status

    print(f"\n{title}")
    print("-" * 60)

    for file in files:
        exists = Path(file).exists()
        print(f"{file:<45} {'PASS' if exists else 'FAIL'}")
        overall_status &= exists


validate_group("Dashboard Core", dashboard_core)
validate_group("Dashboard Components", dashboard_components)
validate_group("Validation", validation_files)

print("\n" + "=" * 60)

if overall_status:
    print("DASHBOARD VALIDATION PASSED")
else:
    print("DASHBOARD VALIDATION FAILED")

print("=" * 60)