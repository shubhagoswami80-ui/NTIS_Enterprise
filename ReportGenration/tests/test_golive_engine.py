from pathlib import Path
import importlib.util

p = Path(__file__).resolve().parents[1] / 'pece_xhr_golive_engine.py'
s = p.read_text(encoding='utf-8')
assert 'fabrication' in s and 'forbidden' in s
assert 'carry_forward' in s and 'cross_symbol_substitution' in s
assert 'completed_with_gaps' in s and 'integrity_gate' in s
assert 'aaData_empty' in s
assert 'AbortController' in s
assert 'PECE_Latest.xlsx' in s
assert 'Status' in s and 'Data' in s
spec=importlib.util.spec_from_file_location('eng',p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
assert m.validate_payload('{"aaData":[[1,2],[3,4]]}')[0]
assert not m.validate_payload('{"aaData":[]}')[0]
assert not m.validate_payload('not-json')[0]
print('PASS: PE/CE go-live engine integrity tests')
