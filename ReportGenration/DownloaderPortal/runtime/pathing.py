from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def render_day_dir(root: str | Path, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    return (
        Path(root).expanduser()
        / now.strftime("%Y")
        / now.strftime("%B").lower()
        / now.strftime("%Y-%m-%d")
    )


def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("._-") or "report"


def final_report_path(job: dict, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    day_dir = render_day_dir(job["output_root"], now)
    day_dir.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(job.get("report_name") or job.get("name") or job["id"])
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    suffix = str(job.get("filename_suffix") or "")
    return day_dir / f"{slug}_{timestamp}{suffix}.xlsx"


def staging_dir(job: dict, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    p = render_day_dir(job["output_root"], now) / "_staging" / job["id"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def trace_dir(job: dict, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    p = render_day_dir(job["output_root"], now) / "_trace" / job["id"]
    p.mkdir(parents=True, exist_ok=True)
    return p
