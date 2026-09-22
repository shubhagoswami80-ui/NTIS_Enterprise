from pathlib import Path
import ast

p = Path(__file__).resolve().parents[1] / "create_pece_diagnostic_copy.py"
s = p.read_text(encoding="utf-8")
ast.parse(s)
assert "62c17d570bb019f5d24147ef10de20ba69090ae7" in s
assert "app_pece_diagnostic.py" in s
assert "hash-object" in s
assert "LIVE_APP.write_text" not in s
print("PASS: diagnostic-copy builder safety/syntax checks")
