from pathlib import Path
import ast, hashlib, subprocess

ROOT = Path(__file__).resolve().parents[1]
app = ROOT / "app_pece_manager_diagnostic.py"
helper = ROOT / "pece_batch220_final_diagnostic.py"

ast.parse(app.read_text(encoding="utf-8"))
ast.parse(helper.read_text(encoding="utf-8"))

text = app.read_text(encoding="utf-8")
assert 'CFG = ROOT.parent / "reports.json"' in text
assert 'PROFILE = ROOT.parent / "browser_profile"' in text
assert 'run_full_220' in text
assert 'pece_full_220' in text
assert 'RUN PE/CE ALL 220 STOCKS — FINAL NATIVE XHR' in text

h = helper.read_text(encoding="utf-8")
assert '00_STARTED.txt' in h
assert 'progress.json' in h
assert 'ERROR.txt' in h
assert 'optSymbol' in h
assert 'concurrency=6' in h
assert 'page.close()' in h

# The diagnostic must never contain production credentials/cookies.
for forbidden in ("PHPSESSID=", "CF_CLEARANCE=", "sessionID=shubh"):
    assert forbidden not in (text + h)

print("PASS: final corrected 220-stock diagnostic safety checks")
