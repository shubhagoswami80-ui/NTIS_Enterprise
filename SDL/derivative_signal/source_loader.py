from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")


def _find_trading_date(path: Path) -> str | None:
    """Find the trading date from the filename first, then from its folder path."""
    match = DATE_RE.search(path.stem)
    if match:
        return match.group("date")

    # Many intraday files do not contain the date in their filename.
    # In that case the selected day folder is the authoritative trading date.
    for part in reversed(path.parts[:-1]):
        match = DATE_RE.fullmatch(part)
        if match:
            return match.group("date")

    return None


def parse_observation_timestamp(path: Path, supplied_timestamp=None) -> pd.Timestamp:
    """
    Resolve an observation timestamp.

    The intraday observation TIME comes from the filesystem timestamp.
    The trading DATE comes from the filename when available, otherwise
    from the YYYY-MM-DD day folder containing the source file.

    This means filenames do not need to contain an intraday timestamp such
    as YYYY-MM-DD_HH-MM. The filesystem timestamp remains the observation
    time used to order snapshots.
    """
    path = Path(path)

    if supplied_timestamp is not None and str(supplied_timestamp).strip():
        return pd.Timestamp(supplied_timestamp)

    if not path.is_file():
        raise FileNotFoundError(f"Source file does not exist: {path}")

    trading_date = _find_trading_date(path)
    if not trading_date:
        raise ValueError(
            "Trading date is missing from the source filename and parent folders. "
            "Expected a YYYY-MM-DD date in the filename or day folder."
        )

    # Keep filesystem modification time as the intraday observation time.
    file_time = pd.Timestamp.fromtimestamp(path.stat().st_mtime)

    return pd.Timestamp(
        f"{trading_date} {file_time.strftime('%H:%M:%S')}"
    )


def read_source(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Source file does not exist: {path}")

    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)

    if suffix == ".csv":
        return pd.read_csv(path)

    raise ValueError(f"Unsupported source format: {path.suffix}")


def discover_daywise_files(
    root: Path,
    trading_date: str | None = None,
) -> list[Path]:
    """Discover Daywise snapshots from the user-selected source folder."""
    root = Path(root)

    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Source folder does not exist: {root}")

    candidates = sorted(
        p
        for p in root.rglob("Daywise_*.xlsx")
        if p.is_file() and not p.name.startswith("~$")
    )

    if trading_date is None:
        return candidates

    return [
        p
        for p in candidates
        if trading_date in p.name or trading_date in str(p.parent)
    ]


def load_primary_snapshot(path: Path, supplied_timestamp=None):
    df = read_source(path)
    df.columns = [str(c).strip() for c in df.columns]

    if "Symbol" not in df.columns:
        raise ValueError("Primary source must contain 'Symbol'.")

    timestamp = parse_observation_timestamp(path, supplied_timestamp)

    return df, timestamp
