from datetime import datetime
from pathlib import Path
import sys

W73 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W73 / "04_REPLAY"))
sys.path.insert(0, str(W73 / "03_LIVE_ADAPTER"))

from w73_point_in_time_replay import W73PointInTimeReplay

class FakeSource:
    def __init__(self, path, timestamp):
        self.path=Path(path); self.timestamp=timestamp

class FakeAdapter:
    def list_intervals(self, month, date):
        return [
            FakeSource("a.xlsx", datetime(2026,9,18,9,18,9)),
            FakeSource("b.xlsx", datetime(2026,9,18,9,23,20)),
        ]
    def read_interval(self, month, date, cutoff):
        return (FakeSource("x.xlsx", cutoff), [], [{"Symbol":"X","ts":cutoff.isoformat()}])

def test_replay_never_crosses_end_cutoff():
    rows = list(W73PointInTimeReplay(FakeAdapter()).run(
        "September26","2026-09-18",
        end=datetime(2026,9,18,9,18,9)
    ))
    assert len(rows) == 1
    assert rows[0].timestamp == datetime(2026,9,18,9,18,9)
