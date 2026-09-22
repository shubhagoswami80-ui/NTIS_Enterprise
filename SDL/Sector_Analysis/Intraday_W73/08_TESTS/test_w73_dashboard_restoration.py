from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "11_DASHBOARD" / "w73_dashboard.py"

def test_dashboard_restored_and_parses():
    assert APP.exists()
    ast.parse(APP.read_text(encoding="utf-8"))

def test_rich_dashboard_contract():
    text = APP.read_text(encoding="utf-8")
    required = [
        "NTIS W73 — Intraday Trader Board",
        "Intraday Setup Readiness",
        "What to Watch Now",
        "Priority Stocks — Select the Strongest Evidence",
        "Alerts / Checkpoints",
        "Selected Stock — Why is it strong?",
        "Point-in-Time Lineage",
        "Filter / Selection Audit",
        "w73_live_ingestor",
        "w73_point_in_time_service",
        "w73_universe_engine",
    ]
    for item in required:
        assert item in text, f"Missing dashboard feature/import: {item}"
