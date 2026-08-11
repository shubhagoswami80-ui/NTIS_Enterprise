"""NET Engineering Toolkit production merge planner.

Migrated from NTIS engineering utility:
NTIS/Tools/EOD_Archive/hmme_production_merge_planner_v2.py

Analyzes similarity modules, groups them by functional keywords, and
produces merge planning reports.
"""

from __future__ import annotations

from pathlib import Path
import difflib
from typing import Iterable, List, Optional

from .common import default_ntis_root, similarity_files, write_csv

SIMILARITY_DIR = "similarity"
OUTPUT_DIR_NAME = "Output"

MASTER_KEYWORDS = [
    "engine",
    "controller",
    "master",
    "manager",
    "pipeline",
    "workflow",
]

FUNCTION_MAP = {
    "CORE": ["engine", "similarity", "calculator", "matcher", "feature"],
    "MEMORY": ["memory", "cache", "repository", "store"],
    "LEARNING": ["learning", "adaptive", "outcome", "training"],
    "DECISION": ["decision", "strategy", "validation"],
    "EXECUTION": ["execution", "trade", "order"],
    "REPORT": ["report", "dashboard", "summary"],
    "CONTROL": ["controller", "workflow", "pipeline", "runner"],
}


def detect_function(filename: str) -> str:
    lower_name = filename.lower()
    for group, keywords in FUNCTION_MAP.items():
        for keyword in keywords:
            if keyword in lower_name:
                return group
    return "UNCLASSIFIED"


def detect_role(filename: str) -> str:
    lower_name = filename.lower()
    return "MASTER_CANDIDATE" if any(keyword in lower_name for keyword in MASTER_KEYWORDS) else "MODULE"


def find_similar(filename: str, files: Iterable[str]) -> str:
    base_name = filename.removesuffix(".py")
    matches: List[str] = []
    for other in files:
        if other == filename:
            continue
        ratio = difflib.SequenceMatcher(None, base_name, other.removesuffix(".py")).ratio()
        if ratio >= 0.65:
            matches.append(other)
    return ",".join(matches)


def generate_reports(root: Optional[Path] = None) -> None:
    ntis_root = root or default_ntis_root()
    output_dir = ntis_root / OUTPUT_DIR_NAME
    files = [path.name for path in similarity_files(ntis_root)]

    records: List[dict[str, str]] = []
    for filename in files:
        records.append(
            {
                "File": filename,
                "Function_Group": detect_function(filename),
                "Role": detect_role(filename),
                "Similar_Files": find_similar(filename, files),
            }
        )

    write_csv(output_dir / "hmme_merge_plan.csv", records, ["File", "Function_Group", "Role", "Similar_Files"])
    write_csv(
        output_dir / "hmme_production_candidates.csv",
        [record for record in records if record["Role"] == "MASTER_CANDIDATE"],
        ["File", "Function_Group", "Role", "Similar_Files"],
    )
    write_csv(
        output_dir / "hmme_unclassified_analysis.csv",
        [record for record in records if record["Function_Group"] == "UNCLASSIFIED"],
        ["File", "Function_Group", "Role", "Similar_Files"],
    )

    summary_lines = [
        "HMME PRODUCTION ARCHITECTURE PLAN",
        "================================",
        "",
        f"Total Files : {len(records)}",
        "",
        *[f"{key}: {value}" for key, value in _count_function_groups(records).items()],
    ]
    (output_dir / "hmme_final_architecture_plan.txt").write_text("\n".join(summary_lines), encoding="utf-8")
    print("Merge planning completed.")


def _count_function_groups(records: List[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        group = record.get("Function_Group", "UNCLASSIFIED")
        counts[group] = counts.get(group, 0) + 1
    return counts


def main() -> int:
    generate_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
