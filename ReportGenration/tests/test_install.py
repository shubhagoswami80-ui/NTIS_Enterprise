from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]

# Production app remains frozen during staging tests.
production_app = root / 'app.py'
assert production_app.exists(), 'production app.py missing'
blob_sha = subprocess.check_output(
    ['git', 'hash-object', str(production_app)], text=True
).strip()
assert blob_sha == '62c17d570bb019f5d24147ef10de20ba69090ae7', blob_sha

# Staged replacement must contain the PE/CE integration; it is not live yet.
staged_app = root / 'app_pece_xhr_golive.py'
app = staged_app.read_text(encoding='utf-8')
assert 'from pece_xhr_golive_engine import run_pece_xhr_batch' in app
assert 'job.get("transport") == "icharts_xhr_batch"' in app
for marker in ['SAVE CONFIGURATION','OPEN / LOGIN SESSION','START DAILY RUN','STOP NOW','+ Add Report','def worker','def select_option','def transform_filename']:
    assert marker in app, marker

job = json.loads((root / 'reports_pece_job.json').read_text(encoding='utf-8'))
assert job['transport'] == 'icharts_xhr_batch'
assert job['interval_minutes'] == 5
assert job['expected_symbol_count'] == 220

inst = (root / 'install_pece_xhr_golive.py').read_text(encoding='utf-8')
assert '62c17d570bb019f5d24147ef10de20ba69090ae7' in inst
assert 'SAFETY STOP' in inst

print('PASS: PE/CE go-live integration safety tests')
