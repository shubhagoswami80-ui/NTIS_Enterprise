from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL_CONFIG = ROOT / "config" / "portal.json"
JOBS_CONFIG = ROOT / "config" / "jobs.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_portal() -> dict:
    return load_json(PORTAL_CONFIG)


def load_jobs() -> list[dict]:
    data = load_json(JOBS_CONFIG)
    return list(data.get("jobs", []))


def save_jobs(jobs: list[dict]) -> None:
    data = load_json(JOBS_CONFIG)
    data["jobs"] = jobs
    JOBS_CONFIG.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
