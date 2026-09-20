from pathlib import Path
from alert_chart.alert_store import AlertStore


def test_store_deduplicates(tmp_path: Path):
    store = AlertStore(tmp_path / "alerts.sqlite3")
    event = {
        "alert_id": "a1", "rule_id": "r1", "trading_date": "2026-09-20",
        "symbol": "ABC", "observation_timestamp": "2026-09-20T10:00:00",
        "direction": "BULLISH", "strength": 84, "payload": {}, "created_at": "x",
    }
    assert store.record_event(event)
    assert not store.record_event(event)
    assert len(store.recent_events()) == 1
