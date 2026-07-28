
"""
NTIS V17 Active Module Cross Check Analyzer

Purpose:
Single-step business classification before cleanup.

Safety:
- No files moved
- No files deleted
- No imports changed
"""

from pathlib import Path


BASE = Path(__file__).parent


RULES = {
    "SCORING_ENGINE": [
        "score", "scoring", "quality", "rank", "factor", "metric"
    ],
    "PATTERN_ENGINE": [
        "pattern", "signal", "trend", "comparison"
    ],
    "PROBABILITY_ENGINE": [
        "probability", "confidence", "prediction", "outcome"
    ],
    "TRADE_VALIDATION": [
        "trade", "risk", "target", "stop"
    ],
    "DATA_PIPELINE": [
        "data", "loader", "import", "source", "bridge",
        "connector", "resolver"
    ],
    "DASHBOARD_REPORTING": [
        "dashboard", "view", "report", "export"
    ],
    "RUNTIME_OPERATIONS": [
        "runtime", "service", "monitor", "control", "manager"
    ],
    "MIGRATION_TOOLS": [
        "activation", "checkpoint", "validation",
        "shadow", "dry_run", "switch", "migration"
    ],
}


def classify(name):

    name = name.lower()

    matches = []

    for category, keywords in RULES.items():
        if any(k in name for k in keywords):
            matches.append(category)

    return matches if matches else ["UNKNOWN_REVIEW"]


def run():

    output = BASE / "V17_ACTIVE_MODULE_REVIEW"
    output.mkdir(exist_ok=True)

    results = {}

    for file in BASE.glob("*_v17.py"):
        results[file.name] = classify(file.name)

    files = {}

    for filename, categories in results.items():
        for category in categories:
            files.setdefault(category, []).append(filename)

    for category, items in files.items():
        (output / f"{category}.txt").write_text(
            "\n".join(sorted(items)),
            encoding="utf-8"
        )

    keep_review = []
    archive = []

    for filename, categories in results.items():
        if "MIGRATION_TOOLS" in categories:
            archive.append(filename)
        else:
            keep_review.append(filename)

    (output / "KEEP_REVIEW_FILES.txt").write_text(
        "\n".join(sorted(keep_review)),
        encoding="utf-8"
    )

    (output / "ARCHIVE_CANDIDATES.txt").write_text(
        "\n".join(sorted(archive)),
        encoding="utf-8"
    )

    print("V17 ACTIVE MODULE CROSS CHECK READY")
    print("KEEP/REVIEW:", len(keep_review))
    print("ARCHIVE CANDIDATES:", len(archive))


if __name__ == "__main__":
    run()
