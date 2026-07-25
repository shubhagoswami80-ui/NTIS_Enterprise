
"""
NTIS Architecture Inventory

Purpose:
Read-only inventory of similarity_core/integration modules.

Safety:
- No file movement
- No deletion
- No imports changed
- No config changes
"""

from pathlib import Path
import csv
from datetime import datetime


BASE = Path(__file__).parent


KEYWORDS = {
    "DATA_RESOLUTION": [
        "data", "resolution", "resolver", "import", "loader", "source"
    ],
    "SCORING": [
        "score", "scoring", "rank", "quality", "factor"
    ],
    "PATTERN": [
        "pattern", "signal", "trend"
    ],
    "PROBABILITY": [
        "probability", "prediction", "confidence", "outcome"
    ],
    "TRADE_VALIDATION": [
        "trade", "risk", "target", "stop", "validation"
    ],
    "DASHBOARD_REPORTING": [
        "dashboard", "report", "export", "view"
    ],
    "RUNTIME_OPERATIONS": [
        "runtime", "service", "monitor", "control", "manager"
    ],
    "GOVERNANCE": [
        "governance", "audit", "compliance"
    ],
    "MIGRATION_CHECKPOINT": [
        "checkpoint", "activation", "shadow", "dry_run", "switch"
    ],
}


def classify(filename):
    name = filename.lower()
    matches = []

    for category, words in KEYWORDS.items():
        if any(word in name for word in words):
            matches.append(category)

    return ",".join(matches) if matches else "UNKNOWN"


def run_inventory():

    files = list(BASE.glob("*.py"))

    report = BASE / "NTIS_ARCHITECTURE_REPORT.csv"

    with report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "File",
            "Category",
            "Size(Bytes)"
        ])

        for file in sorted(files):
            writer.writerow([
                file.name,
                classify(file.name),
                file.stat().st_size
            ])

    summary = {}

    for file in files:
        category = classify(file.name)
        summary[category] = summary.get(category, 0) + 1

    print("=" * 60)
    print("NTIS ARCHITECTURE INVENTORY COMPLETE")
    print("=" * 60)
    print("TOTAL FILES:", len(files))

    for key, value in sorted(summary.items()):
        print(key, value)

    print("REPORT:", report.name)


if __name__ == "__main__":
    run_inventory()
