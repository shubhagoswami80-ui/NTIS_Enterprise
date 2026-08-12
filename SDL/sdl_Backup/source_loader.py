from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

TIMESTAMP_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})[_-](?P<time>\d{2})[-_:](?P<minute>\d{2})")

def parse_observation_timestamp(path: Path, supplied_timestamp=None):
    if supplied_timestamp:
        return pd.Timestamp(supplied_timestamp)

    match = TIMESTAMP_RE.search(path.stem)
    if not match:
        raise ValueError(
            "Observation timestamp is missing. Use a filename like "
            "SDL_Snapshot_2026-08-11_10-00.xlsx or supply an explicit timestamp."
        )
    return pd.Timestamp(f"{match.group('date')} {match.group('time')}:{match.group('minute')}")

def read_source(path: Path) -> pd.DataFrame:
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
    timestamp = parse_observation_timestamp(path, supplied_timestamp)
    return df, timestamp
