from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
m = json.loads((ROOT/"10_DOCS/FINAL_PORTAL_FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
required = ["app.py","config.py","data_store.py","strategy.py","views.py",
"02_FEATURE_ENGINE/w73_exact_v8_live_engine.py",
"06_ALERTS/w73_live_decision_service.py",
"11_DASHBOARD/w73_dashboard.py",
"11_DASHBOARD/start_w73_dashboard.ps1",
"11_DASHBOARD/stop_w73_dashboard.ps1",
"12_INTEGRATION/w73_entrypoint.py"]
missing = [x for x in required if not (ROOT/x).exists()]
result = {"status":"PASS_FREEZE_MANIFEST" if not missing else "FAIL_FREEZE_MANIFEST",
"missing_required_files":missing,"decision":m["decision"],
"strategy_changes":m["strategy_changes"],"dashboard_changes":m["dashboard_changes"],
"exact_orb_source_proven":False}
print(json.dumps(result, indent=2))
raise SystemExit(0 if not missing else 1)
