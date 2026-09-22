from pathlib import Path

def test_dashboard_and_launcher_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "11_DASHBOARD" / "w73_dashboard.py").exists()
    assert (root / "11_DASHBOARD" / "start_w73_dashboard.ps1").exists()

def test_integration_boundary_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "12_INTEGRATION" / "w73_entrypoint.py").exists()
