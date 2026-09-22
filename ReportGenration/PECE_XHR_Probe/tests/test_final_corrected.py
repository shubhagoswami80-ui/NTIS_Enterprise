from pathlib import Path
import ast
r=Path(__file__).resolve().parents[1]
for n in ("pece_batch220_native_fast.py","build_final_diagnostic.py"):
    ast.parse((r/n).read_text(encoding="utf-8"))
b=(r/"build_final_diagnostic.py").read_text(encoding="utf-8")
assert 'ROOT.parent / "reports.json"' in b
assert 'ROOT.parent / "browser_profile"' in b
assert 'run_full_220' in b
print("PASS: final corrected 220-stock native-XHR bundle checks")
