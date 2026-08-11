"""NET Engineering Toolkit project scanner.

Migrated from NTIS engineering utility:
NTIS/Tools/EOD_Archive/NTIS_EOD_File_Function_Mapper_v2.py

The tool scans NTIS Python sources, extracts file, function, class,
and import metadata, and writes CSV reports.
"""

from __future__ import annotations

from pathlib import Path
import ast
from datetime import datetime
from typing import Iterable, List, Sequence, Tuple

from .common import default_ntis_root, write_csv_rows

DEFAULT_IGNORE = {".git", ".venv", "__pycache__", "Architecture_Report", "intraday"}


def ignored(path: Path, ignore: Iterable[str] = DEFAULT_IGNORE) -> bool:
    return any(part in ignore for part in path.parts)


def collect_ast_info(file_path: Path) -> Tuple[List[Sequence[str]], List[Sequence[str]], List[Sequence[str]]]:
    functions: List[Sequence[str]] = []
    classes: List[Sequence[str]] = []
    imports: List[Sequence[str]] = []

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append([str(file_path), node.name, ast.get_docstring(node) or ""])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append([str(file_path), node.name, ast.get_docstring(node) or ""])
        elif isinstance(node, ast.Import):
            for name in node.names:
                imports.append([str(file_path), name.name])
        elif isinstance(node, ast.ImportFrom):
            imports.append([str(file_path), node.module or ""])

    return functions, classes, imports


def scan_project(root: Path, ignore: Iterable[str] = DEFAULT_IGNORE) -> Tuple[List[Sequence[str]], List[Sequence[str]], List[Sequence[str]], List[Sequence[str]]]:
    files: List[Sequence[str]] = []
    functions: List[Sequence[str]] = []
    classes: List[Sequence[str]] = []
    imports: List[Sequence[str]] = []

    for file_path in root.rglob("*.py"):
        if ignored(file_path, ignore):
            continue

        relative_path = str(file_path.relative_to(root))
        files.append([relative_path])

        try:
            file_functions, file_classes, file_imports = collect_ast_info(file_path)
            functions.extend(file_functions)
            classes.extend(file_classes)
            imports.extend(file_imports)
        except SyntaxError:
            continue
        except Exception:
            continue

    return files, functions, classes, imports


def main(ntis_root: Path | None = None, output_dir: Path | None = None) -> int:
    root = ntis_root or default_ntis_root()
    output = output_dir or root / "Tools" / "Architecture_Report"
    output.mkdir(parents=True, exist_ok=True)

    files, functions, classes, imports = scan_project(root)

    write_csv_rows(output / "NTIS_File_Map.csv", ["File"], files)
    write_csv_rows(output / "NTIS_Function_Map.csv", ["File", "Function", "Description"], functions)
    write_csv_rows(output / "NTIS_Class_Map.csv", ["File", "Class", "Description"], classes)
    write_csv_rows(output / "NTIS_Module_Dependency_Map.csv", ["Source", "Import"], imports)

    print("Completed:", datetime.now())
    print("Output:", output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
