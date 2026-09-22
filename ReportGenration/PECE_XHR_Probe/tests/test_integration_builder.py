from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / 'integrate_symbol_discovery.py'
t = p.read_text(encoding='utf-8')
ast.parse(t)
assert 'app_pece_manager_diagnostic.py' in t
assert 'pece_control_discovery' in t
assert 'TARGET.write_text' in t
# The builder must not contain direct writes to the live production files.
assert 'Path("app.py").write_text' not in t
assert "Path('app.py').write_text" not in t
assert 'Path("reports.json").write_text' not in t
assert "Path('reports.json').write_text" not in t
assert 'browser_profile' not in t
assert 'PHPSESSID' not in t
assert 'sessionID' not in t
print('PASS: symbol discovery integration builder safety test')
