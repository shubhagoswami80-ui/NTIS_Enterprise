from pathlib import Path

print("="*60)
print("NTIS INTRADAY REPLAY VALIDATION")
print("="*60)

files = [
"intraday_historical_replay_engine.py",
"intraday_outcome_engine.py",
"intraday_accuracy_tracker.py",
"intraday_probability_calibration.py",
"run_intraday_replay_validation.py"
]

ok = True

for f in files:
    status = Path(f).exists()
    print(f"{f:<45}", "PASS" if status else "FAIL")
    ok = ok and status

print("="*60)

if ok:
    print("REPLAY FOUNDATION READY")
else:
    print("REPLAY FOUNDATION INCOMPLETE")

print("="*60)
