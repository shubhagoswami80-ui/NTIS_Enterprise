from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

def test_dashboard_uses_live_decision_service():
    p = ROOT / "11_DASHBOARD" / "w73_dashboard.py"
    text = p.read_text(encoding="utf-8")
    assert "w73_live_decision_service" in text
    assert "evaluate_latest_maturity" in text

def test_stop_script_uses_fixed_w73_port_without_reserved_pid_variable():
    p = ROOT / "11_DASHBOARD" / "stop_w73_dashboard.ps1"
    text = p.read_text(encoding="utf-8")
    assert "$expectedPort=9005" in text
    assert "$targetPid" in text
    assert "$pid" not in text.lower()
