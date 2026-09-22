from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class W73Config:
    root: Path
    validation_csv: Path
    live_input: Path | None
    cache_dir: Path
    max_rows: int = 10000

    @classmethod
    def from_environment(cls) -> "W73Config":
        root = Path(__file__).resolve().parent
        # Source of truth: baseline is always INSIDE W73.
        validation = root / "00_BASELINE" / "chronological_validation_corrected.csv"
        live_raw = os.getenv("NTIS_W73_LIVE_INPUT", "").strip()
        live = Path(live_raw) if live_raw else None
        cache = root / ".cache"
        cache.mkdir(exist_ok=True)
        return cls(root, validation, live, cache)
