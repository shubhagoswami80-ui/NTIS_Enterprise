from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from .sector_models import SectorSnapshot

SECTOR_ALIASES = [
    "Sector", "Sector Name", "Sector_Name", "Industry", "Industry Name",
    "SectorName", "SECTOR", "sector",
]
SYMBOL_ALIASES = [
    "Symbol", "SYMBOL", "Ticker", "Stock", "Security", "Company", "Name",
]
TIMESTAMP_ALIASES = [
    "Timestamp", "timestamp", "Observation Timestamp", "Observation_Timestamp",
    "DateTime", "Datetime", "Time", "Snapshot Time", "Snapshot_Time",
]

_SECTOR_FILE_TOKENS = ("sector_summary", "sector summary", "sector-summary")
_SUPPORTED_SUFFIXES = {".xlsx", ".xlsm", ".csv"}


def _find_col(columns: Iterable[str], aliases: list[str]) -> str | None:
    cols = list(columns)
    norm = {str(c).strip().lower(): c for c in cols}
    for alias in aliases:
        hit = norm.get(alias.lower())
        if hit is not None:
            return hit
    for c in cols:
        lc = str(c).strip().lower()
        if any(alias.lower() in lc for alias in aliases):
            return c
    return None


def _column_series(frame: pd.DataFrame, label) -> pd.Series | None:
    """Return one physical column even when workbook headers are duplicated."""
    if label is None:
        return None
    for idx, col in enumerate(frame.columns):
        if col == label:
            return frame.iloc[:, idx]
    # Fallback for headers differing only by whitespace/case.
    target = str(label).strip().lower()
    for idx, col in enumerate(frame.columns):
        if str(col).strip().lower() == target:
            return frame.iloc[:, idx]
    return None


def observation_time(path: Path) -> pd.Timestamp:
    # Windows creation/arrival time is the authoritative filesystem snapshot time.
    # Filename timestamps are deliberately ignored.
    try:
        return pd.Timestamp.fromtimestamp(path.stat().st_ctime).tz_localize(None)
    except Exception:
        return pd.NaT


def _read_workbook(path: Path) -> list[tuple[str, pd.DataFrame]]:
    out = []
    try:
        sheets = pd.read_excel(path, sheet_name=None)
        for name, frame in sheets.items():
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                out.append((str(name), frame))
    except Exception:
        pass
    return out


def _is_sector_summary_file(path: Path) -> bool:
    name = path.name.lower()
    return path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES and any(
        token in name for token in _SECTOR_FILE_TOKENS
    )



def find_sector_summary_candidates(root: str | Path) -> list[Path]:
    """Fast metadata-only discovery. Does not open any workbook."""
    root = Path(root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        [p for p in root.rglob("*") if _is_sector_summary_file(p)],
        key=lambda p: (observation_time(p), str(p).lower()),
    )


def load_sector_summary_snapshot(path: str | Path) -> list[SectorSnapshot]:
    """Load one Sector Summary file only."""
    path = Path(path).expanduser().resolve()
    if not _is_sector_summary_file(path):
        return []
    observed = observation_time(path)
    if pd.isna(observed):
        return []

    if path.suffix.lower() == ".csv":
        try:
            frames = [("CSV", pd.read_csv(path))]
        except Exception:
            frames = []
    else:
        frames = _read_workbook(path)

    snapshots: list[SectorSnapshot] = []
    for sheet, frame in frames:
        if frame is None or frame.empty:
            continue
        sector_col = _find_col(frame.columns, SECTOR_ALIASES)
        symbol_col = _find_col(frame.columns, SYMBOL_ALIASES)
        if sector_col is None:
            continue

        work = frame.copy()
        sector_series = _column_series(work, sector_col)
        if sector_series is None:
            continue
        work["sector"] = sector_series.astype(str).str.strip()

        if symbol_col is not None:
            symbol_series = _column_series(work, symbol_col)
            if symbol_series is not None:
                work["symbol"] = symbol_series

        work["_source_sheet"] = sheet
        work["_source_file"] = str(path)
        work["_observed_at"] = observed

        snapshots.append(
            SectorSnapshot(
                path=path,
                observed_at=observed,
                frame=work,
                sector_column="sector",
                symbol_column="symbol" if symbol_col is not None else None,
            )
        )
    return snapshots


def discover_sector_snapshots(
    root: str | Path,
    progress_callback: Callable[[int, int, str, int], None] | None = None,
) -> list[SectorSnapshot]:
    """Full discovery retained for compatibility/replay and first build."""
    candidates = find_sector_summary_candidates(root)
    snapshots: list[SectorSnapshot] = []
    total = len(candidates)
    if progress_callback is not None:
        progress_callback(0, total, "Sector Summary scan started", 0)

    for index, path in enumerate(candidates, start=1):
        if progress_callback is not None:
            progress_callback(index - 1, total, f"Scanning {path.name}", len(snapshots))
        loaded = load_sector_summary_snapshot(path)
        snapshots.extend(loaded)
        if progress_callback is not None:
            progress_callback(index, total, f"Checked {path.name}", len(snapshots))

    if progress_callback is not None:
        progress_callback(total, total, "Sector Summary scan finished", len(snapshots))
    return snapshots

def load_replay_snapshot(
    snapshots: list[SectorSnapshot],
    selected_at: pd.Timestamp,
) -> SectorSnapshot | None:
    valid = [
        s for s in snapshots
        if pd.notna(s.observed_at) and s.observed_at <= selected_at
    ]
    return max(valid, key=lambda s: s.observed_at) if valid else None


def aggregate_sector_rows(snapshot: SectorSnapshot) -> pd.DataFrame:
    frame = snapshot.frame.copy()
    sector_col = snapshot.sector_column

    if not sector_col or sector_col not in frame.columns:
        return pd.DataFrame()

    # Canonical sector field is guaranteed by discover_sector_snapshots().
    if sector_col != "sector":
        series = _column_series(frame, sector_col)
        if series is None:
            return pd.DataFrame()
        frame["sector"] = series

    frame["sector"] = frame["sector"].astype(str).str.strip()
    frame = frame[
        frame["sector"].notna()
        & (frame["sector"] != "")
        & (frame["sector"].str.lower() != "nan")
    ].copy()

    if frame.empty:
        return frame

    # The source stores breadth as one field such as "13 / 0 / 0".
    # Split it into explicit Adv/Dec/Unchg values so the intelligence engine
    # can measure participation correctly instead of treating breadth as raw text.
    breadth_col = _find_col(frame.columns, ["Adv/ Dec/ Unchg", "Adv/Dec/Unchg", "Adv Dec Unchg", "Advance/Decline/Unchanged"])
    if breadth_col:
        breadth_series = _column_series(frame, breadth_col)
        if breadth_series is not None:
            parts = breadth_series.astype(str).str.extract(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")
            frame["adv"] = pd.to_numeric(parts[0], errors="coerce")
            frame["dec"] = pd.to_numeric(parts[1], errors="coerce")
            frame["unchg"] = pd.to_numeric(parts[2], errors="coerce")

    aliases = {
        "price_chg": [
            "Price Chg (%)", "Price Chg %", "Price Chg",
            "Price Change %", "Change %", "Change", "Pct Change", "% Change",
        ],
        "volume_chg": [
            "Volume Chg (%)", "Volume Chg %", "Volume Chg",
            "Volume Change %", "Volume Change",
        ],
        "oi_chg": [
            "OI Chg (%)", "OI Chg %", "OI Chg",
            "OI Change %", "OI Change",
        ],
        "rollover": ["Rollover (%)", "Rollover %", "Rollover"],
        "buildup": ["Buildup", "Build Up", "OI Buildup"],
        "pcr_chg": ["PCR Chg %", "PCR Chg", "PCR Change %", "PCR Change"],
        "iv_chg": ["IV Chg %", "IV Chg", "IV Change %", "IV Change"],
        "ce_oi_chg": [
            "Tol CE OI Chg (%)", "Tot CE OI Chg %", "Tol CE OI Chg",
            "Tot CE OI Chg", "CE OI Chg %", "CE OI Chg",
        ],
        "pe_oi_chg": [
            "Tol PE OI Chg (%)", "Tot PE OI Chg %", "Tol PE OI Chg",
            "Tot PE OI Chg", "PE OI Chg %", "PE OI Chg",
        ],
        "pe_ce_oi_chg": [
            "Tol PE-CE OI Chg (%)", "Tot PE-CE OI Chg %",
            "Tol PE-CE OI Chg", "Tot PE-CE OI Chg",
            "PE-CE OI Chg", "PE CE OI Chg",
        ],
        "straddle": [
            "ATM Straddle %", "ATM Straddle", "Straddle %",
            "Straddle",
        ],
    }

    for target, candidates in aliases.items():
        col = _find_col(frame.columns, candidates)
        if col and target not in frame.columns:
            series = _column_series(frame, col)
            if series is not None:
                frame[target] = pd.to_numeric(series, errors="coerce")

    numeric = [
        "price_chg", "volume_chg", "oi_chg", "rollover",
        "pcr_chg", "iv_chg", "ce_oi_chg", "pe_oi_chg",
        "pe_ce_oi_chg", "straddle",
    ]
    for col in numeric:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    return frame
