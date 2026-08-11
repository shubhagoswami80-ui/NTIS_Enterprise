"""NET Engineering Toolkit active dependency mapper.

Migrated from NTIS engineering utility:
NTIS/Tools/EOD_Archive/hmme_active_dependency_mapper.py

Analyzes active similarity modules, computes import/reference counts, and
classifies files by group heuristics.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable, List

from .common import default_ntis_root, similarity_files, write_csv

SIMILARITY_DIR = "similarity"
OUTPUT_DIR_NAME = "Output"

GROUP_RULES = {
    "CORE_ENGINE": ["engine", "core", "similarity", "calculator"],
    "CONTROLLER": ["controller", "runner", "pipeline", "workflow"],
    "MEMORY": ["memory", "cache", "repository"],
    "LEARNING": ["learning", "adaptive", "training", "outcome"],
    "DECISION": ["decision", "strategy", "validation"],
    "EXECUTION": ["execution", "trade", "order"],
    "REPORTING": ["report", "dashboard", "summary"],
    "UTILITY": ["config", "utils", "helper", "schema"],
}


def build_patterns(module_name: str) -> tuple[re.Pattern, re.Pattern]:
    import_pattern = re.compile(
        rf"(import\s+{re.escape(module_name)}|from\s+{re.escape(module_name)}\s+import)",
        re.IGNORECASE,
    )
    reference_pattern = re.compile(rf"\b{re.escape(module_name)}\b", re.IGNORECASE)
    return import_pattern, reference_pattern


def scan_dependencies(files: Iterable[Path]) -> List[dict[str, str]]:
    results: List[dict[str, str]] = []

    for file_path in files:
        imported_by: List[str] = []
        referenced_by: List[str] = []
        module_name = file_path.stem
        import_pattern, reference_pattern = build_patterns(module_name)

        for other in files:
            if other == file_path:
                continue

            try:
                content = other.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            if import_pattern.search(content):
                imported_by.append(other.name)
            elif reference_pattern.search(content):
                referenced_by.append(other.name)

        results.append(
            {
                "File": file_path.name,
                "Size": str(file_path.stat().st_size),
                "Imported_By": str(len(imported_by)),
                "Referenced_By": str(len(referenced_by)),
            }
        )

    return results


def assign_group(filename: str) -> str:
    name = filename.lower()
    for group, keywords in GROUP_RULES.items():
        for keyword in keywords:
            if keyword in name:
                return group
    return "UNCLASSIFIED"


def write_summary(path: Path, results: List[dict[str, str]]) -> None:
    counts: dict[str, int] = {}
    for row in results:
        classification = row.get("Group", "UNCLASSIFIED")
        counts[classification] = counts.get(classification, 0) + 1

    summary_lines = [
        "HMME ACTIVE REDUCTION SUMMARY",
        "============================",
        "",
        f"Active Files : {len(results)}",
        "",
        *[f"{key}    {value}" for key, value in counts.items()],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(summary_lines), encoding="utf-8")


def main() -> int:
    ntis_root = default_ntis_root()
    output_dir = ntis_root / OUTPUT_DIR_NAME
    files = similarity_files(ntis_root)
    results = scan_dependencies(files)

    for row in results:
        row["Group"] = assign_group(row["File"])

    write_csv(output_dir / "hmme_active_dependency_map.csv", results, ["File", "Size", "Imported_By", "Referenced_By", "Group"])
    write_csv(output_dir / "hmme_module_groups.csv", [{"File": row["File"], "Group": row["Group"]} for row in results], ["File", "Group"])
    write_summary(output_dir / "hmme_core_reduction_summary.txt", results)

    print("Reports created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
