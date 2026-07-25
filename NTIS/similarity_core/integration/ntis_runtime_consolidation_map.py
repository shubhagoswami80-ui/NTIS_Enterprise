
"""
NTIS Runtime Consolidation Map

Purpose:
Analyze runtime-related modules only.

Read-only:
- No file movement
- No deletion
- No code changes
"""

from pathlib import Path
import csv


BASE = Path(__file__).parent


GROUPS = {
    "RUNTIME_CORE_CANDIDATE": [
        "runtime_control",
        "runtime_engine",
        "runtime_core",
        "runtime_flow"
    ],
    "HEALTH_MONITORING": [
        "health",
        "stability",
        "resilience",
        "refresh"
    ],
    "SERVICE_OPERATIONS": [
        "service",
        "operation",
        "operations"
    ],
    "VALIDATION": [
        "validation",
        "check",
        "checkpoint"
    ],
    "GOVERNANCE": [
        "governance",
        "audit",
        "compliance"
    ],
    "CONNECTOR": [
        "connector",
        "bridge",
        "adapter"
    ],
    "MANAGEMENT": [
        "manager",
        "control"
    ]
}


def classify(name):

    n = name.lower()

    matches = []

    for group, keywords in GROUPS.items():
        if any(k in n for k in keywords):
            matches.append(group)

    return ",".join(matches) if matches else "UNKNOWN"


def run():

    files = [
        f for f in BASE.glob("*_v17.py")
        if "runtime" in f.name.lower()
    ]

    report = BASE / "RUNTIME_CONSOLIDATION_MAP.csv"

    with report.open("w", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        writer.writerow([
            "File",
            "Runtime_Group",
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
        group = classify(file.name)
        summary[group] = summary.get(group, 0) + 1

    print("=" * 60)
    print("NTIS RUNTIME CONSOLIDATION MAP READY")
    print("=" * 60)
    print("RUNTIME FILES:", len(files))

    for key, value in sorted(summary.items()):
        print(key, value)

    print("REPORT:", report.name)


if __name__ == "__main__":
    run()
