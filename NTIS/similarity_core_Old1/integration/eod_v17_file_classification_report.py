
"""
NTIS V17 File Classification Report

Purpose:
Classify V17 integration files before cleanup.

No files moved.
No files deleted.
No imports changed.
"""

from pathlib import Path


BASE = Path(__file__).parent

KEEP_FILES = {
    "eod_data_resolution_core_v17.py",
    "eod_replay_dashboard_core_v17.py",
    "eod_runtime_control_core_v17.py",
    "eod_service_management_core_v17.py",
    "eod_governance_audit_core_v17.py",
    "eod_production_control_core_v17.py",
    "eod_final_integration_core_v17.py",
}


def classify_file(name):

    if name in KEEP_FILES:
        return "KEEP"

    archive_keywords = [
        "activation",
        "checkpoint",
        "validation",
        "shadow",
        "dry_run",
        "switch",
        "migration",
    ]

    if any(k in name.lower() for k in archive_keywords):
        return "ARCHIVE"

    review_keywords = [
        "dashboard",
        "runtime",
        "service",
        "data",
        "replay",
        "connector",
        "manager",
        "engine",
    ]

    if any(k in name.lower() for k in review_keywords):
        return "REVIEW"

    return "REVIEW"


def generate_report():

    reports = {
        "KEEP_LIST.txt": [],
        "ARCHIVE_LIST.txt": [],
        "REVIEW_LIST.txt": [],
    }

    for file in BASE.glob("*_v17.py"):
        category = classify_file(file.name)
        reports[f"{category}_LIST.txt"].append(file.name)

    output = BASE / "V17_Classification_Report"
    output.mkdir(exist_ok=True)

    for filename, items in reports.items():
        (output / filename).write_text(
            "\n".join(sorted(items)),
            encoding="utf-8"
        )

    print("V17 FILE CLASSIFICATION REPORT READY")
    for key, value in reports.items():
        print(key, len(value))


if __name__ == "__main__":
    generate_report()
