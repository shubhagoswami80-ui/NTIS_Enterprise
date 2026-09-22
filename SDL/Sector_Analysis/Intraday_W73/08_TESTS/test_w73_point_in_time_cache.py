from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_LIVE_ADAPTER"))

from w73_source_adapter import SourceFile
from w73_point_in_time_cache import W73PointInTimeCache
from w73_canonical_observation import canonicalize


def test_cache_round_trip(tmp_path: Path):
    source = SourceFile(
        tmp_path / "Daywise_Price_and_OI_Summary_x_20260918_092320.xlsx",
        datetime(2026, 9, 18, 9, 23, 20),
    )
    records = [{"Symbol": "TEST", "ATM Straddle Price": 10.5, "IV": None}]
    cache = W73PointInTimeCache(tmp_path / "cache")
    path = cache.write_interval(source, "2026-09-18", records)
    assert path.exists()
    rows = cache.read_interval("2026-09-18", source.timestamp)
    assert len(rows) == 1
    assert rows[0].symbol == "TEST"
    assert rows[0].raw["IV"] is None


def test_canonical_mapping_does_not_fill_missing():
    row = canonicalize({"Symbol": "TEST", "IV": None})
    assert row["Symbol"] == "TEST"
    assert row["IV"] is None
    assert "Price Chg %" in row
    assert row["Price Chg %"] is None


def test_cache_path_is_point_in_time(tmp_path: Path):
    cache = W73PointInTimeCache(tmp_path)
    p1 = cache.path_for("2026-09-18", datetime(2026, 9, 18, 9, 23, 20))
    p2 = cache.path_for("2026-09-18", datetime(2026, 9, 18, 9, 28, 29))
    assert p1 != p2
