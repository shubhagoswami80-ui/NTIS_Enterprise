from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=[
    "00_BASELINE/maturity_feature_matrix.csv",
    "00_BASELINE/strategy_baseline_v1_tied_max.json",
    "02_FEATURE_ENGINE/w73_exact_v8_live_engine.py",
    "03_LIVE_ADAPTER/w73_live_ingestor.py",
    "06_ALERTS/w73_live_decision_service.py",
    "11_DASHBOARD/w73_dashboard.py",
    "11_DASHBOARD/start_w73_dashboard.ps1",
    "11_DASHBOARD/stop_w73_dashboard.ps1",
    "12_INTEGRATION/w73_entrypoint.py",
]
missing=[p for p in REQUIRED if not (ROOT/p).exists()]
print("STATUS=" + ("PASS_DEPLOYMENT_GATE" if not missing else "FAIL_DEPLOYMENT_GATE"))
print("MISSING=" + (",".join(missing) if missing else "0"))
if missing:
    raise SystemExit(2)
