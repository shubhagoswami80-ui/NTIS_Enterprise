"""NET Engineering Toolkit dependency analyzer.

Migrated from NTIS engineering utility:
NTIS/Tools/EOD_Archive/hmme_dependency_scanner_v4.py

The analyzer evaluates Python module dependencies inside the NTIS similarity
workspace and classifies files for keep/review/safe-delete based on imports
and symbol references.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional, Sequence

from .common import default_ntis_root, read_csv_rows, similarity_files, write_csv

SIMILARITY_DIR_NAME = "similarity"
OUTPUT_DIR_NAME = "Output"

IMPORT_PATTERN = re.compile(
    r"(import\s+{module}|from\s+{module}\s+import)",
    re.IGNORECASE,
)
REFERENCE_PATTERN = re.compile(r"\b{module}\b", re.IGNORECASE)


@dataclass(frozen=True)
class DependencyResult:
    file: str
    imported_by: int
    referenced_by: int
    classification: str


def build_import_patterns(filename: str) -> tuple[re.Pattern, re.Pattern]:
    module_name = filename.removesuffix(".py")
    import_pattern = re.compile(
        IMPORT_PATTERN.pattern.format(module=re.escape(module_name)),
        re.IGNORECASE,
    )
    reference_pattern = re.compile(
        REFERENCE_PATTERN.pattern.format(module=re.escape(module_name)),
        re.IGNORECASE,
    )
    return import_pattern, reference_pattern


def scan_file_dependencies(filename: str, source_files: Sequence[Path]) -> tuple[List[str], List[str]]:
    import_pattern, reference_pattern = build_import_patterns(filename)
    imported: List[str] = []
    referenced: List[str] = []

    for source_file in source_files:
        if source_file.name == filename:
            continue

        try:
            content = source_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if import_pattern.search(content):
            imported.append(str(source_file))
        elif reference_pattern.search(content):
            referenced.append(str(source_file))

    return imported, referenced


def classify_dependency(imported: Sequence[str], referenced: Sequence[str]) -> str:
    if imported:
        return "KEEP"
    if referenced:
        return "REVIEW"
    return "SAFE_DELETE"


def write_results(output_path: Path, results: Sequence[DependencyResult]) -> None:
    rows = [
        {
            "File": result.file,
            "Imported_By": str(result.imported_by),
            "Referenced_By": str(result.referenced_by),
            "Classification": result.classification,
        }
        for result in results
    ]
    write_csv(output_path, rows, ["File", "Imported_By", "Referenced_By", "Classification"])


def process_file_list(
    input_path: Path,
    source_files: Sequence[Path],
    results: List[DependencyResult],
) -> None:
    rows = read_csv_rows(input_path)
    for row in rows:
        filename = row["File"]
        imported, referenced = scan_file_dependencies(filename, source_files)
        results.append(
            DependencyResult(
                file=filename,
                imported_by=len(imported),
                referenced_by=len(referenced),
                classification=classify_dependency(imported, referenced),
            )
        )


def analyze_dependencies(root: Optional[Path] = None) -> list[DependencyResult]:
    ntis_root = root or default_ntis_root()
    source_files = similarity_source_files(ntis_root)
    output_dir = ntis_root / OUTPUT_DIR_NAME

    results: List[DependencyResult] = []
    process_file_list(output_dir / "hmme_review_delete_candidate.csv", source_files, results)
    process_file_list(output_dir / "hmme_review_required.csv", source_files, results)

    return results


def write_analysis_reports(root: Optional[Path] = None) -> None:
    ntis_root = root or default_ntis_root()
    output_dir = ntis_root / OUTPUT_DIR_NAME
    results = analyze_dependencies(ntis_root)

    write_results(output_dir / "hmme_dependency_analysis.csv", results)

    classifications = {"KEEP": [], "REVIEW": [], "SAFE_DELETE": []}
    for result in results:
        classifications.setdefault(result.classification, []).append(result)

    for classification, items in classifications.items():
        write_results(
            output_dir / f"hmme_dependency_{classification.lower()}.csv",
            items,
        )

    print("\n".join([
        f"{classification}: {len(items)}"
        for classification, items in classifications.items()
    ]))
    print("Dependency analysis completed")


def main() -> int:
    write_analysis_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
