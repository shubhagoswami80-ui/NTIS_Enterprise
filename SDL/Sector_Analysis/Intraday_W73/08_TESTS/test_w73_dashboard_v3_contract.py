from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_dashboard_uses_live_decision_service():
    text = (ROOT / "11_DASHBOARD" / "w73_dashboard.py").read_text(encoding="utf-8")
    assert "w73_live_decision_service" in text
    assert "QUALIFIED" in text
    assert "NOT_READY" in text

def test_dashboard_keeps_fail_closed_vocabulary():
    text = (ROOT / "11_DASHBOARD" / "w73_dashboard.py").read_text(encoding="utf-8")
    assert "NOT_READY" in text
    assert "evaluate_latest_maturity" in text
