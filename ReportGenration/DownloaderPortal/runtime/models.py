from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobState:
    job_id: str
    status: str = "idle"
    message: str = ""
    last_started: str = ""
    last_finished: str = ""
    last_success: str = ""
    next_run: str = ""
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    running: bool = False
    page_open: bool = False
    last_error: str = ""
    discovery: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "message": self.message,
            "last_started": self.last_started,
            "last_finished": self.last_finished,
            "last_success": self.last_success,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "running": self.running,
            "page_open": self.page_open,
            "last_error": self.last_error,
            "discovery": self.discovery,
        }


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
