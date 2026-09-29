from __future__ import annotations

from dataclasses import dataclass, asdict
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
    run_count: int = 0
    success_count: int = 0
    partial_count: int = 0
    failure_count: int = 0
    page_open: bool = False
    heartbeat_at: str = ""
    current_stage: str = "IDLE"
    current_detail: str = ""
    started_at: str = ""

    def dict(self):
        return asdict(self)


class StateStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.states: dict[str, JobState] = {}
        self.load()

    def get(self, job_id: str) -> JobState:
        if job_id not in self.states:
            self.states[job_id] = JobState(job_id)
        return self.states[job_id]

    def load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for job_id, raw in (data or {}).items():
                if isinstance(raw, dict):
                    raw = dict(raw)
                    raw["job_id"] = job_id
                    self.states[job_id] = JobState(**{
                        k: raw[k] for k in JobState.__dataclass_fields__ if k in raw
                    })
        except Exception:
            self.states = {}

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {job_id: state.dict() for job_id, state in self.states.items()}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
