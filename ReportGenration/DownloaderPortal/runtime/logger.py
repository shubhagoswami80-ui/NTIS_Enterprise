from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading


class PortalLogger:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def log(self, message: str, job_id: str = "portal") -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp} [{job_id}] {message}\n"
        with self.lock:
            (self.root / f"{datetime.now():%Y-%m-%d}.log").open(
                "a", encoding="utf-8"
            ).write(line)
