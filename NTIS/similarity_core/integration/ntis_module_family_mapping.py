
"""
NTIS Module Family Mapping Report

Purpose:
Group integration modules by functional family.

Read-only analysis:
- No file movement
- No deletion
- No code changes
"""

from pathlib import Path
import csv


BASE = Path(__file__).parent


FAMILIES = {
    "DATA_RESOLUTION": ["data", "resolution", "resolver", "import", "loader"],
    "SCORING": ["score", "scoring", "rank", "quality", "factor"],
    "PATTERN": ["pattern", "signal", "trend"],
    "PROBABILITY": ["probability", "prediction", "confidence", "outcome"],
    "TRADE_VALIDATION": ["trade", "risk", "target", "stop"],
    "DASHBOARD": ["dashboard", "report", "view", "export"],
    "RUNTIME": ["runtime", "service", "control", "health", "monitor"],
    "GOVERNANCE": ["governance", "audit", "compliance"],
    "CONNECTOR": ["connector", "bridge", "adapter"],
    "VALIDATION": ["validation", "checkpoint", "check"],
}


def classify(name):
    name = name.lower()
    matches = []

    for family, words in FAMILIES.items():
        if any(word in name for word in words):
            matches.append(family)

    return ",".join(matches) if matches else "UNKNOWN"


def run():

    files = list(BASE.glob("*_v17.py"))

    report = BASE / "NTIS_MODULE_FAMILY_REPORT.csv"

    with report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "File",
            "Family"
        ])

        for file in sorted(files):
            writer.writerow([
                file.name,
                classify(file.name)
            ])

    summary = {}

    for file in files:
        family = classify(file.name)
        summary[family] = summary.get(family, 0) + 1

    print("=" * 60)
    print("NTIS MODULE FAMILY MAPPING READY")
    print("=" * 60)
    print("TOTAL FILES:", len(files))

    for k, v in sorted(summary.items()):
        print(k, v)

    print("REPORT:", report.name)


if __name__ == "__main__":
    run()
