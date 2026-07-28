
"""
NTIS Module Ownership Mapping

Purpose:
Read-only ownership classification before consolidation.

No file movement.
No deletion.
No code changes.
"""

from pathlib import Path
import csv


BASE = Path(__file__).parent


RULES = {
    "DATA_RESOLUTION": ["data", "resolution", "resolver", "import", "loader"],
    "SCORING": ["score", "scoring", "rank", "quality", "factor"],
    "PATTERN": ["pattern", "signal", "trend"],
    "PROBABILITY": ["probability", "prediction", "confidence", "outcome"],
    "TRADE_VALIDATION": ["trade", "risk", "target", "stop"],
    "DASHBOARD": ["dashboard", "report", "export", "view"],
    "GOVERNANCE": ["governance", "audit", "compliance"],
    "CONNECTOR": ["connector", "bridge", "adapter"],
    "VALIDATION": ["validation", "checkpoint", "check"],
    "RUNTIME": ["runtime", "service", "control", "health", "monitor"],
}


def classify(name):
    n = name.lower()
    matches = []

    for owner, keywords in RULES.items():
        if any(k in n for k in keywords):
            matches.append(owner)

    if not matches:
        return "REVIEW_REQUIRED", "LOW", "No clear ownership keyword"

    if len(matches) == 1:
        return matches[0], "HIGH", "Single domain match"

    return matches[0], "MEDIUM", "Multiple domain indicators"


def run():

    files = list(BASE.glob("*_v17.py"))

    report = BASE / "NTIS_MODULE_OWNERSHIP_REPORT.csv"

    with report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "File",
            "Recommended_Owner",
            "Confidence",
            "Reason"
        ])

        for file in sorted(files):
            owner, confidence, reason = classify(file.name)
            writer.writerow([
                file.name,
                owner,
                confidence,
                reason
            ])

    print("=" * 60)
    print("NTIS MODULE OWNERSHIP MAPPING READY")
    print("=" * 60)
    print("TOTAL FILES:", len(files))
    print("REPORT:", report.name)


if __name__ == "__main__":
    run()
