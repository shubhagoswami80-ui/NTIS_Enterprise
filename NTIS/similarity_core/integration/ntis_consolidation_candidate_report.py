
"""
NTIS Consolidation Candidate Report

Purpose:
Read-only analysis of integration modules.

No files moved.
No files deleted.
No imports changed.
"""

from pathlib import Path
import csv


BASE = Path(__file__).parent


def classify(name, size):

    n = name.lower()

    if "core" in n:
        return "KEEP"

    merge_words = [
        "runtime",
        "dashboard",
        "governance",
        "validation",
        "checkpoint",
        "manager",
        "bridge",
        "connector",
        "service",
        "control"
    ]

    archive_words = [
        "backup",
        "legacy",
        "old",
        "migration",
        "shadow",
        "dry_run"
    ]

    if any(x in n for x in archive_words):
        return "ARCHIVE_CANDIDATE"

    if any(x in n for x in merge_words):
        return "MERGE_CANDIDATE"

    if size < 200:
        return "REVIEW"

    return "REVIEW"


def run():

    report = BASE / "NTIS_CONSOLIDATION_CANDIDATES.csv"

    files = list(BASE.glob("*.py"))

    with report.open("w", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        writer.writerow([
            "File",
            "Size(Bytes)",
            "Decision"
        ])

        for file in sorted(files):
            writer.writerow([
                file.name,
                file.stat().st_size,
                classify(file.name, file.stat().st_size)
            ])

    summary = {}

    for file in files:
        decision = classify(file.name, file.stat().st_size)
        summary[decision] = summary.get(decision, 0) + 1

    print("=" * 60)
    print("NTIS CONSOLIDATION CANDIDATE REPORT READY")
    print("=" * 60)
    print("TOTAL FILES:", len(files))

    for k, v in sorted(summary.items()):
        print(k, v)

    print("REPORT:", report.name)


if __name__ == "__main__":
    run()
