from datetime import datetime
from pathlib import Path
import sys

ADAPTER_DIR = Path(__file__).resolve().parents[1] / "03_LIVE_ADAPTER"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))

from w73_source_adapter import W73SourceAdapter, W73SourceConfig


def test_day_scope_is_non_recursive(tmp_path: Path):
    day = tmp_path / "September26" / "2026-09-18"
    day.mkdir(parents=True)
    (day / "Daywise_Price_and_OI_Summary_x_20260918_091809.xlsx").write_bytes(b"")
    nested = day / "nested"
    nested.mkdir()
    (nested / "Daywise_Price_and_OI_Summary_x_20260918_092000.xlsx").write_bytes(b"")

    files = W73SourceAdapter(W73SourceConfig(tmp_path)).list_intervals(
        "September26", "2026-09-18"
    )
    assert len(files) == 1


def test_cutoff_excludes_future(tmp_path: Path):
    day = tmp_path / "September26" / "2026-09-18"
    day.mkdir(parents=True)
    for t in ("091809", "092320", "094507"):
        (day / f"Daywise_Price_and_OI_Summary_x_20260918_{t}.xlsx").write_bytes(b"")

    files = W73SourceAdapter(W73SourceConfig(tmp_path)).list_intervals(
        "September26", "2026-09-18",
        cutoff=datetime(2026, 9, 18, 9, 30, 0),
    )
    assert [x.timestamp.strftime("%H%M%S") for x in files] == ["091809", "092320"]


def test_missing_day_fails(tmp_path: Path):
    try:
        W73SourceAdapter(W73SourceConfig(tmp_path)).list_intervals(
            "September26", "2026-09-19"
        )
    except FileNotFoundError:
        return
    raise AssertionError("Expected missing day to fail")
