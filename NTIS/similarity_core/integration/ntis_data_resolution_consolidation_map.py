
"""
NTIS Data Resolution Consolidation Map

Purpose:
Analyze data-resolution related modules before consolidation.

Read-only:
- No file movement
- No deletion
- No import changes
- No config changes
"""

from pathlib import Path
import csv


BASE = Path(__file__).parent


RULES = {
    "KEEP_DATA_CORE": [
        "data_resolution_core",
        "data_core"
    ],
    "DATA_INGESTION": [
        "import",
        "loader",
        "source",
        "ingest",
        "collector"
    ],
    "DATA_RESOLUTION": [
        "data_resolution",
        "resolver",
        "resolution"
    ],
    "DATA_VALIDATION": [
        "validation",
        "quality",
        "schema",
        "check"
    ],
    "DATA_ADAPTER_CONNECTOR": [
        "adapter",
        "connector",
        "bridge"
    ],
    "MOVE_TO_RUNTIME_REVIEW": [
        "runtime",
        "service",
        "monitor",
        "control"
    ],
    "ARCHIVE_REVIEW": [
        "backup",
        "legacy",
        "old",
        "migration",
        "shadow"
    ]
}


def classify(name):
    n = name.lower()
    matches = []

    for group, keywords in RULES.items():
        if any(k in n for k in keywords):
            matches.append(group)

    if not matches:
        return "REVIEW_REQUIRED"

    return ",".join(matches)


def run():

    files = [
        f for f in BASE.glob("*_v17.py")
        if any(x in f.name.lower() for x in [
            "data", "resolution", "resolver",
            "import", "loader", "schema",
            "source", "adapter", "connector"
        ])
    ]

    report = BASE / "DATA_RESOLUTION_CONSOLIDATION_PLAN.csv"

    with report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "File",
            "Proposed_Action",
            "Size(Bytes)"
        ])

        for file in sorted(files):
            writer.writerow([
                file.name,
                classify(file.name),
                file.stat().st_size
            ])

    print("=" * 60)
    print("DATA RESOLUTION CONSOLIDATION MAP READY")
    print("=" * 60)
    print("FILES ANALYZED:", len(files))
    print("REPORT:", report.name)


if __name__ == "__main__":
    run()
