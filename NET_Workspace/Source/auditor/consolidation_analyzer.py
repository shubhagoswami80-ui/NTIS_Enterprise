"""NET Engineering Toolkit consolidation analyzer.

Migrated from NTIS engineering utility:
NTIS/Tools/EOD_Archive/hmme_consolidation_analyzer_v3.py

Classifies review candidates based on filename heuristics and writes
classification reports.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .common import default_ntis_root, read_csv_rows, write_csv

OUTPUT_DIR_NAME = "Output"
INPUT_FILENAME = "hmme_review_list.csv"

CORE_KEYWORDS = [
    "engine",
    "controller",
    "bridge",
    "pipeline",
    "runner",
    "manager",
    "adapter",
    "schema",
    "validator",
]

SUPPORT_KEYWORDS = [
    "config",
    "model",
    "loader",
    "builder",
    "utility",
    "helper",
    "cache",
]

MERGE_KEYWORDS = [
    "optimizer",
    "monitor",
    "tracker",
    "analyzer",
    "generator",
    "report",
    "service",
    "handler",
]

ARCHIVE_KEYWORDS = [
    "release",
    "experiment",
    "module",
    "test",
    "demo",
]


def classify(filename: str, size: int) -> str:
    normalized = filename.lower()

    if size < 40:
        return "DELETE_CANDIDATE"

    for keyword in CORE_KEYWORDS:
        if keyword in normalized:
            return "KEEP_CORE"

    for keyword in SUPPORT_KEYWORDS:
        if keyword in normalized:
            return "KEEP_SUPPORT"

    for keyword in MERGE_KEYWORDS:
        if keyword in normalized:
            return "MERGE"

    for keyword in ARCHIVE_KEYWORDS:
        if keyword in normalized:
            return "ARCHIVE"

    return "REVIEW_REQUIRED"


def generate_reports(base_dir: Optional[Path] = None) -> None:
    root = base_dir or default_ntis_root()
    output_dir = root / OUTPUT_DIR_NAME
    input_path = output_dir / INPUT_FILENAME

    if not input_path.exists():
        print("Missing:", input_path)
        return

    rows = read_csv_rows(input_path)
    results: List[dict[str, str]] = []

    for row in rows:
        filename = row["File"]
        size = int(row.get("Size(Bytes)", "0"))
        results.append(
            {
                "File": filename,
                "Size": str(size),
                "Classification": classify(filename, size),
            }
        )

    reports = {
        "KEEP_CORE": "hmme_review_keep_core.csv",
        "KEEP_SUPPORT": "hmme_review_keep_support.csv",
        "MERGE": "hmme_review_merge.csv",
        "ARCHIVE": "hmme_review_archive.csv",
        "DELETE_CANDIDATE": "hmme_review_delete_candidate.csv",
        "REVIEW_REQUIRED": "hmme_review_required.csv",
    }

    for classification, filename in reports.items():
        write_csv(
            output_dir / filename,
            [row for row in results if row["Classification"] == classification],
            ["File", "Size", "Classification"],
        )

    fieldnames = ["File", "Size", "Classification"]
    summary = [
        "HMME REVIEW CLASSIFICATION",
        "==========================",
        "",
        *fieldnames,
    ]

    counts: dict[str, int] = {}
    for row in results:
        counts[row["Classification"]] = counts.get(row["Classification"], 0) + 1

    summary.extend(["", *[f"{key}: {value}" for key, value in counts.items()]])
    (output_dir / "hmme_review_summary.txt").write_text("\n".join(summary), encoding="utf-8")

    print("Reports created.")


def main() -> int:
    generate_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
