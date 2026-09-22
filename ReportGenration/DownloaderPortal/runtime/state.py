from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json


@dataclass
class JobState:
    job_id: str
    state: str = "IDLE"
    last_run: str = ""
    next_run: str = ""
    duration_seconds: float = 0.0
    download_status: str = "NOT_RUN"
    processing_status: str = "NOT_RUN"
    error_count: int = 0
    last_error_category: str = ""
    last_message: str = ""

    def dict(self):
        return asdict(self)


class StateStore:
    def __init__(self):
        self.states: dict[str, JobState] = {}

    def get(self, job_id: str) -> JobState:
        if job_id not in self.states:
            self.states[job_id] = JobState(job_id)
        return self.states[job_id]
