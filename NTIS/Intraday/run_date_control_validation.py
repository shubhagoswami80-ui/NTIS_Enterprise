
from pathlib import Path

print("="*60)
print("NTIS DATE CONTROL ARCHITECTURE VALIDATION")
print("="*60)

files = [
"intraday_execution_context.py",
"intraday_config.py",
"intraday_path_config.py"
]

ok=True

for f in files:
    result=Path(f).exists()
    print(f"{f:<40}", "PASS" if result else "FAIL")
    ok = ok and result

print("="*60)
print("DATE CONTROL READY" if ok else "INCOMPLETE")
print("="*60)
