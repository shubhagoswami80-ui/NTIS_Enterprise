from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_has_fixed_port_variable():
    p = ROOT / "11_DASHBOARD" / "start_w73_dashboard.ps1"
    text = p.read_text(encoding="utf-8")
    assert "$Port=9005" in text
    assert "--server.port\",$Port" in text


def test_dashboard_uses_live_decision_service():
    p = ROOT / "11_DASHBOARD" / "w73_dashboard.py"
    text = p.read_text(encoding="utf-8")
    assert "w73_live_decision_service" in text
    assert "QUALIFIED" in text
    assert "NOT_READY" in text
