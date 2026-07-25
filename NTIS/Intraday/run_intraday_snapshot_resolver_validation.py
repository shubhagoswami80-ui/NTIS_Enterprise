from pathlib import Path

print("="*60)
print("NTIS INTRADAY SNAPSHOT RESOLVER VALIDATION")
print("="*60)

files = [
    "intraday_latest_snapshot_resolver.py",
    "run_intraday_snapshot_resolver_validation.py"
]

ok = True

for f in files:
    status = Path(f).exists()
    print(f"{f:<50}", "PASS" if status else "FAIL")
    ok = ok and status

print("="*60)

print(
    "SNAPSHOT RESOLVER READY"
    if ok
    else "SNAPSHOT RESOLVER INCOMPLETE"
)

print("="*60)
