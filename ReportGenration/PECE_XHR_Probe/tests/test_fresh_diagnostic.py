from pathlib import Path
import py_compile
ROOT=Path(__file__).resolve().parents[1]
app=ROOT/"app_pece_manager_diagnostic.py"
helper=ROOT/"pece_symbol_event_diagnostic.py"
assert app.exists()
assert helper.exists()
a=app.read_text(encoding="utf-8")
h=helper.read_text(encoding="utf-8")
assert 'CFG = ROOT.parent / "reports.json"' in a
assert 'PROFILE = ROOT.parent / "browser_profile"' in a
assert 'LOGS = ROOT / "logs"' in a
assert 'from pece_symbol_event_diagnostic import discover_symbol_change' in a
assert 'if command == "pece_symbol_change":' in a
assert 'key="pece_symbol_change"' in a
assert 'SYMBOL_SELECTOR' in h and '#optSymbol' in h
assert 'select_option(test)' in h
assert 'select_option(original)' in h
assert '_safe_post_data' in h
assert 'context.new_page()' in h
assert 'page.close()' in h
py_compile.compile(str(app),doraise=True)
py_compile.compile(str(helper),doraise=True)
print("PASS: final v3 diagnostic generated-file validation")
