from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "11_DASHBOARD" / "w73_dashboard.py"
SERVICE = ROOT / "06_ALERTS" / "w73_live_decision_service.py"

def test_live_decision_service_present():
    assert SERVICE.exists()
    ast.parse(SERVICE.read_text(encoding="utf-8"))

def test_dashboard_can_resolve_alert_module():
    text = APP.read_text(encoding="utf-8")
    assert "ROOT / \"06_ALERTS\"" in text
    assert "w73_live_decision_service" in text
    assert "evaluate_latest_maturity" in text
    assert "NOT_READY" in text
