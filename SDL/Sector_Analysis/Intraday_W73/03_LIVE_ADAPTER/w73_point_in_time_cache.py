from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json
import os
import sys
from typing import Any

_HERE = Path(__file__).resolve().parent
_ADAPTER_DIR = _HERE
if str(_ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(_ADAPTER_DIR))

from w73_source_adapter import W73SourceAdapter, SourceFile


@dataclass(frozen=True)
class W73Observation:
    trading_date: str
    source_timestamp: str
    source_file: str
    symbol: str
    raw: dict[str, Any]


class W73PointInTimeCache:
    """Local W73 cache. External source remains read-only."""

    def __init__(self, root: Path | None = None) -> None:
        configured = os.getenv("NTIS_W73_CACHE_ROOT", "")
        self.root = Path(configured) if configured else (
            root if root is not None else Path(__file__).resolve().parents[1] / ".cache" / "point_in_time"
        )

    def path_for(self, trading_date: str, timestamp: datetime) -> Path:
        return self.root / trading_date / timestamp.strftime("%H%M%S") / "observations.jsonl"

    def write_interval(
        self,
        source: SourceFile,
        trading_date: str,
        records: list[dict[str, Any]],
    ) -> Path:
        path = self.path_for(trading_date, source.timestamp)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replace at the W73 cache only.
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for record in records:
                symbol = str(record.get("Symbol", "")).strip()
                if not symbol:
                    continue
                obs = W73Observation(
                    trading_date=trading_date,
                    source_timestamp=source.timestamp.isoformat(),
                    source_file=source.path.name,
                    symbol=symbol,
                    raw=dict(record),
                )
                fh.write(json.dumps(asdict(obs), ensure_ascii=False, default=str) + "\n")
        tmp.replace(path)
        return path

    def read_interval(self, trading_date: str, timestamp: datetime) -> list[W73Observation]:
        path = self.path_for(trading_date, timestamp)
        if not path.exists():
            return []
        out: list[W73Observation] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    data = json.loads(line)
                    out.append(W73Observation(**data))
        return out


def cache_selected_interval(
    adapter: W73SourceAdapter,
    cache: W73PointInTimeCache,
    month_folder: str,
    trading_date: str,
    *,
    cutoff: datetime | None = None,
) -> Path:
    source, _header, records = adapter.read_interval(
        month_folder, trading_date, cutoff=cutoff
    )
    return cache.write_interval(source, trading_date, records)
