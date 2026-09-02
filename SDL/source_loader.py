from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


# Kept for backward compatibility/documentation only. It is NOT used as the
# authoritative timestamp source.
TIMESTAMP_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})[_-]"
    r"(?P<time>\d{2})[-_:](?P<minute>\d{2})"
)


def parse_observation_timestamp(path: Path, supplied_timestamp=None):
    """
    Return the authoritative observation timestamp for a source file.

    SDL's source-time contract is filesystem creation/arrival time. Filename
    conventions are deliberately ignored because the earliest source files
    did not contain an intraday timestamp and future naming changes must not
    affect chronology.

    On Windows, st_ctime is the file creation time. The project runs on
    Windows, so this is the intended source timestamp.

    An explicitly supplied timestamp remains authoritative for callers that
    already have the observation timestamp from the pipeline.
    """
    if supplied_timestamp is not None:
        return pd.Timestamp(supplied_timestamp)

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Source file does not exist: {path}")

    try:
        # st_ctime is a Unix-epoch timestamp. Passing it directly to
        # pd.Timestamp(int) interprets the integer as nanoseconds, which
        # incorrectly produces an epoch-era value such as 1970-01-01
        # 00:00:01. Use the epoch value explicitly and convert it to IST.
        creation_epoch = path.stat().st_ctime
        timestamp = pd.Timestamp.fromtimestamp(
            creation_epoch,
            tz="Asia/Kolkata",
        )
        return timestamp.tz_localize(None)
    except Exception as exc:
        raise ValueError(
            f"Unable to read source file creation timestamp: {path}"
        ) from exc


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
