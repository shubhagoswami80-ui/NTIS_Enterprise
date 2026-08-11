"""NET Engineering Toolkit similarity core dependency map.

Migrated from NTIS engineering utility:
NTIS/Tools/EOD_Archive/ntis_similarity_core_dependency_map.py

Builds a dependency map of similarity_core_clean files, identifies required,
archive, and unknown review candidates.
"""

from __future__ import annotations

from pathlib import Path
import ast
from typing import Iterable

from .common import default_ntis_root, write_csv_rows

SIMILARITY_CORE_DIR_NAME = "similarity_core_clean"
ENTRY_POINTS = [
    "production_runtime.py",
    "eod_data_resolution_activation_check_v17.py",
    "eod_data_resolution_core_v17.py",
]


def similarity_core_files(root: Path) -> dict[str, Path]:
    directory = root / SIMILARITY_CORE_DIR_NAME
    files: dict[str, Path] = {}
    for path in directory.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        files[path.name] = path
    return files


def extract_imports(file_path: Path) -> list[str]:
    imports: list[str] = []
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    imports.append(item.name.split(".")[-1] + ".py")
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[-1] + ".py")
    except Exception:
        pass
    return imports


def build_dependency_graph(files: dict[str, Path]) -> dict[str, list[str]]:
    return {name: [dep for dep in extract_imports(path) if dep in files] for name, path in files.items()}


def resolve_dependencies(graph: dict[str, list[str]], start: str) -> set[str]:
    visited: set[str] = set()

    def walk(node: str) -> None:
        if node in visited:
            return
        visited.add(node)
        for child in graph.get(node, []):
            walk(child)

    walk(start)
    return visited


def analyze(root: Path | None = None) -> tuple[list[list[str]], list[list[str]], list[list[str]]]:
    ntis_root = root or default_ntis_root()
    files = similarity_core_files(ntis_root)
    graph = build_dependency_graph(files)
    required: set[str] = set()

    for entry in ENTRY_POINTS:
        if entry in graph:
            required |= resolve_dependencies(graph, entry)

    keep: list[list[str]] = []
    archive: list[list[str]] = []
    unknown: list[list[str]] = []

    for name in sorted(files):
        if name in required:
            keep.append([name, "KEEP_REQUIRED"])
        elif any(keyword in name.lower() for keyword in ["_old", "_backup", "_copy", "_orig"]):
            archive.append([name, "ARCHIVE_CANDIDATE"])
        else:
            unknown.append([name, "UNKNOWN_REVIEW"])

    return keep, archive, unknown


def write_reports(root: Path | None = None) -> None:
    ntis_root = root or default_ntis_root()
    directory = ntis_root / SIMILARITY_CORE_DIR_NAME
    keep, archive, unknown = analyze(ntis_root)
    write_csv_rows(directory / "KEEP_REQUIRED_FILES.csv", ["File", "Classification"], keep)
    write_csv_rows(directory / "ARCHIVE_FILES.csv", ["File", "Classification"], archive)
    write_csv_rows(directory / "UNKNOWN_FILES.csv", ["File", "Classification"], unknown)


def main() -> int:
    write_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
