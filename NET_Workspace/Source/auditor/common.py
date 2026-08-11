"""Shared NET Engineering Toolkit auditor helpers."""

from __future__ import annotations

from pathlib import Path
import csv
from typing import Iterable, List, Sequence


def default_ntis_root() -> Path:
    return Path(__file__).resolve().parents[3] / "NTIS"


def write_csv(path: Path, rows: Iterable[dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_csv_rows(path: Path, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(headers))
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("File")]


def similarity_files(root: Path, directory_name: str = "similarity") -> List[Path]:
    similarity_dir = root / directory_name
    return sorted(similarity_dir.glob("*.py")) if similarity_dir.exists() else []
