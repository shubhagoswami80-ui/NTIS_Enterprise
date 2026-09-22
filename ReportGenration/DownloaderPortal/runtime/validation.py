from __future__ import annotations

from pathlib import Path


REQUIRED_FIELDS = [
    "id", "name", "report_name", "url", "transport",
    "browser_required", "browser_profile",
    "group_id", "scheduler_id", "enabled", "environment",
    "action", "selection", "selection_selector",
    "submit_selector", "download_selector", "wait_seconds",
    "interval_minutes", "timeout_seconds", "retry_count",
    "request_gap_ms", "jitter_ms", "batch_size", "concurrency",
    "backoff_initial_ms", "backoff_max_ms", "http_429_policy",
    "expected_symbol_count", "output_root", "processing_root",
    "final_output_root", "filename_pattern", "filename_suffix",
    "filename_rule", "validation_required", "required_sheets",
    "alert_severity", "test_live", "overlap_policy",
]


def validate_job(job: dict) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in job:
            errors.append(f"missing field: {field}")
    if not str(job.get("output_root", "")).strip():
        errors.append("output_root is required")
    if int(job.get("interval_minutes", 0) or 0) < 1:
        errors.append("interval_minutes must be >= 1")
    if int(job.get("concurrency", 0) or 0) < 1:
        errors.append("concurrency must be >= 1")
    if int(job.get("retry_count", 0) or 0) < 0:
        errors.append("retry_count must be >= 0")
    return errors


def validate_output(path: Path, required_sheets: list[str]) -> tuple[bool, str]:
    if not path.exists():
        return False, "final output file missing"
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        missing = [s for s in required_sheets if s not in wb.sheetnames]
        wb.close()
        if missing:
            return False, f"missing required sheets: {missing}"
        return True, "ok"
    except Exception as exc:
        return False, f"invalid workbook: {exc}"
