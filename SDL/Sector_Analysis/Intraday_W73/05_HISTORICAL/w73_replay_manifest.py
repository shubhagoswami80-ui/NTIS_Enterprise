from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json

@dataclass
class ReplayManifest:
    trading_date: str
    month_folder: str
    start: str | None
    end: str | None
    source_root: str
    intervals: int = 0
    rows: int = 0

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
