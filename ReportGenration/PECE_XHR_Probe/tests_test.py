from pathlib import Path
p=Path(__file__).resolve().parents[0]/"pece_xhr_integrity_engine.py"
s=p.read_text(encoding='utf-8')
assert 'fabrication' in s and 'forbidden' in s
assert 'completed_with_gaps' in s and 'integrity_gate' in s
assert 'aaData_empty' in s
assert 'retry_failed' in s
print('PASS: PE/CE integrity/no-fabrication architecture checks')
