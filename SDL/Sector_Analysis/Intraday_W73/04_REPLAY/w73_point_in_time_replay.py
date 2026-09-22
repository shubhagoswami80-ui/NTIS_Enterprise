from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

from w73_source_adapter import W73SourceAdapter

@dataclass(frozen=True)
class ReplayObservation:
    trading_date: str
    timestamp: datetime
    source_file: str
    rows: list[dict]

class W73PointInTimeReplay:
    """Chronological replay; never supplies rows after the requested cutoff."""

    def __init__(self, adapter: W73SourceAdapter):
        self.adapter = adapter

    def run(
        self, month_folder: str, trading_date: str,
        start: datetime | None = None, end: datetime | None = None
    ) -> Iterator[ReplayObservation]:
        for source in self.adapter.list_intervals(month_folder, trading_date):
            ts = source.timestamp
            if start and ts < start: continue
            if end and ts > end: continue
            _source, _header, rows = self.adapter.read_interval(
                month_folder, trading_date, cutoff=ts
            )
            yield ReplayObservation(trading_date, ts, source.path.name, rows)
