from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Iterator

_HERE = Path(__file__).resolve().parent
_ADAPTER_DIR = _HERE.parent / "03_LIVE_ADAPTER"
if str(_ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(_ADAPTER_DIR))

from w73_source_adapter import W73SourceAdapter, SourceFile


@dataclass(frozen=True)
class ReplayPoint:
    source: SourceFile
    header: list[str]
    records: list[dict[str, object]]


class W73ReplayEngine:
    """Replay interval snapshots without future-data leakage."""

    def __init__(self, adapter: W73SourceAdapter | None = None) -> None:
        self.adapter = adapter or W73SourceAdapter()

    def points(
        self,
        month_folder: str,
        trading_date: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Iterator[ReplayPoint]:
        files = self.adapter.list_intervals(
            month_folder, trading_date, cutoff=end
        )
        for source in files:
            if start is not None and source.timestamp < start:
                continue
            header, records = self.adapter.read_workbook(source.path)
            yield ReplayPoint(source, header, records)
