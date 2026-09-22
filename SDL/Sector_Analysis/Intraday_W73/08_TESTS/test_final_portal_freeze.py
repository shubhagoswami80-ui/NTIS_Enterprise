import json
from pathlib import Path

def test_final_freeze_manifest():
    p = Path(__file__).parents[1] / "10_DOCS" / "FINAL_PORTAL_FREEZE_MANIFEST.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["decision"] == "PORTAL_OPERATIONAL_FREEZE_EXACT_ORB_NOT_PROVEN"
    assert d["strategy_changes"] is False
    assert d["dashboard_changes"] is False
    assert d["final_gate"]["source_covers_09_15"] is False
