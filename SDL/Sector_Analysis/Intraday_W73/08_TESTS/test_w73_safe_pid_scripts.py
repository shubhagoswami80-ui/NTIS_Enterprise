from pathlib import Path

def test_safe_start_and_stop_scripts_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "11_DASHBOARD" / "start_w73_dashboard.ps1").exists()
    assert (root / "11_DASHBOARD" / "stop_w73_dashboard.ps1").exists()

def test_scripts_use_fixed_w73_port():
    root = Path(__file__).resolve().parents[1]
    start = (root / "11_DASHBOARD" / "start_w73_dashboard.ps1").read_text(encoding="utf-8")
    stop = (root / "11_DASHBOARD" / "stop_w73_dashboard.ps1").read_text(encoding="utf-8")
    assert "$Port=9005" in start
    assert "$expectedPort" in stop
    assert "REFUSING_TO_STOP_UNVERIFIED_PID" in stop

def test_stop_does_not_use_broad_python_kill():
    root = Path(__file__).resolve().parents[1]
    stop = (root / "11_DASHBOARD" / "stop_w73_dashboard.ps1").read_text(encoding="utf-8")
    assert "Get-Process python" not in stop
    assert "taskkill /IM python.exe" not in stop
