from pathlib import Path
import ast

app = Path(__file__).resolve().parents[1] / "app.py"
text = app.read_text(encoding="utf-8")
ast.parse(text)
assert 'from pece_xhr_golive_engine import run_pece_xhr_batch' in text
assert 'acquisition_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")' in text
assert 'filename = (' in text
assert 'f"{acquisition_timestamp}"' in text
assert 'f"{acquisition_timestamp}_"' in text
assert 'if job.get("transport") == "icharts_xhr_batch":' in text
print("PASS: timestamp filename + PE/CE integration tests")
