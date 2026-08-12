from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


TIMESTAMP_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})[_-]"
    r"(?P<time>\d{2})[-_:](?P<minute>\d{2})"
)


def parse_observation_timestamp(path: Path, supplied_timestamp=None):
    if supplied_timestamp:
        return pd.Timestamp(supplied_timestamp)

    match = TIMESTAMP_RE.search(path.stem)
    if not match:
        raise ValueError(
            "Observation timestamp is missing. Supply an explicit timestamp "
            "or use a filename containing YYYY-MM-DD_HH-MM."
        )

    return pd.Timestamp(
        f"{match.group('date')} "
        f"{match.group('time')}:"
        f"{match.group('minute')}"
    )


def read_source(path: Path) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Source file does not exist: {path}")

    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(path)

    if suffix == ".csv":
        return pd.read_csv(path)

    raise ValueError(f"Unsupported source format: {path.suffix}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    if "Symbol" not in out.columns:
        raise ValueError("Primary source must contain 'Symbol'.")

    return out


def load_primary_snapshot(path: Path, supplied_timestamp=None):
    df = normalize_columns(read_source(path))
    timestamp = parse_observation_timestamp(
        Path(path),
        supplied_timestamp,
    )
    return df, timestamp


def discover_daywise_files(
    root: Path,
    trading_date: str | None = None,
) -> list[Path]:
    """
    Discover Daywise Excel snapshots recursively from the external
    historical repository. Source files are never modified.
    """
    root = Path(root)

    if not root.exists():
        raise FileNotFoundError(
            f"Historical source root does not exist: {root}"
        )

    candidates = sorted(
        p for p in root.rglob("Daywise_*.xlsx")
        if p.is_file()
    )

    if trading_date is None:
        return candidates

    return [
        p for p in candidates
        if trading_date in p.name
        or trading_date in str(p.parent)
    ]
