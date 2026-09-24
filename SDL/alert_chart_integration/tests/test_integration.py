import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alert_chart_integration import build_alert_snapshot

def test_timestamp_preserved():
    x=build_alert_snapshot({"symbol":"ABC"},{"symbol":"ABC"},trading_date="2026-09-21",observation_timestamp="2026-09-21 10:00:00")
    assert x["current"]["observation_timestamp"]=="2026-09-21 10:00:00"
    assert x["is_selection_gate"] is False
def test_no_wall_clock_field():
    x=build_alert_snapshot({"symbol":"ABC"})
    assert "observation_timestamp" not in x["current"]
