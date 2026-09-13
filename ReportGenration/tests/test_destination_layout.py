from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
engine = (ROOT / "pece_xhr_golive_engine.py").read_text(encoding="utf-8")
assert 'time.strftime("%Y", dt)' in engine
assert 'time.strftime("%B", dt).lower()' in engine
assert 'time.strftime("%Y-%m-%d", dt)' in engine
assert 'f"PECE_{cycle_id}.xlsx"' in engine
assert 'PECE_Latest.xlsx' not in engine
assert 'f"PECE_{cycle_id}.json"' in engine
assert 'Per-symbol payloads' in engine
print("PASS: PE/CE timestamped date-folder layout tests")
