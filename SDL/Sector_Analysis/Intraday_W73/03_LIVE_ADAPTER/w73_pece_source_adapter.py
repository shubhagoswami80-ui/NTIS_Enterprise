"""
NTIS W73 - PE/CE source adapter
READ-ONLY external source adapter.

The adapter deliberately does not derive PE-CE percentage from separate
PE% and CE% percentages. It accepts only the direct PE-CE percentage field
published by the PECE source.

Supported source roots:
    NTIS_W73_PECE_SOURCE_ROOT
    fallback: D:\My-data\Share_P&L\Ichart Data\Screenshot\PECE_Volume

Expected PECE report columns include:
    Symbol
    Time
    Snapshot
    Diff(PE-CE OI Chg)
    Diff(PE-CE OI Chg %)

If Snapshot is absent, file mtime is NOT promoted to market time. The
record remains matchable only when an explicit acquisition boundary is
supplied by the caller; otherwise it is rejected as causally unsafe.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_PECE_ROOT = Path(
    r"D:\My-data\Share_P&L\Ichart Data\Screenshot\PECE_Volume"
)

_TS_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%H:%M:%S",
)


def _parse_ts(value: Any, trading_date: str | None = None) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    try:
        ts = pd.to_datetime(text, errors="coerce")
        if pd.notna(ts):
            ts = ts.to_pydatetime()
            if trading_date and ts.year == 1900:
                d = datetime.fromisoformat(trading_date)
                ts = ts.replace(year=d.year, month=d.month, day=d.day)
            return ts.replace(tzinfo=None)
    except Exception:
        pass
    for fmt in _TS_PATTERNS:
        try:
            ts = datetime.strptime(text, fmt)
            if fmt == "%H:%M:%S" and trading_date:
                d = datetime.fromisoformat(trading_date)
                ts = ts.replace(year=d.year, month=d.month, day=d.day)
            return ts
        except ValueError:
            continue
    return None


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _find_column(columns, aliases: tuple[str, ...]) -> str | None:
    wanted = {_norm(x) for x in aliases}
    for col in columns:
        if _norm(col) in wanted:
            return str(col)
    return None


@dataclass(frozen=True)
class PECERecord:
    trading_date: str
    symbol: str
    observation_time: datetime | None
    snapshot_time: datetime | None
    pece_oi_chg: float | None
    pece_oi_chg_pct: float | None
    source_file: str
    file_created_time: datetime | None
    raw: dict[str, Any]

    @property
    def direct_pct_state(self) -> str | None:
        value = self.pece_oi_chg_pct
        if value is None:
            return None
        if value > 0:
            return "POS"
        if value < 0:
            return "NEG"
        return "ZERO"


class PECEReadOnlyAdapter:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(
            root or os.environ.get("NTIS_W73_PECE_SOURCE_ROOT") or DEFAULT_PECE_ROOT
        )

    def discover(self, trading_date: str) -> list[Path]:
        """
        Non-recursive day partition selection.

        The folder date is authoritative. No filename date token is used to
        establish the trading date.
        """
        day = self.root / datetime.fromisoformat(trading_date).strftime("%Y") / \
              datetime.fromisoformat(trading_date).strftime("%B").lower() / trading_date
        if not day.exists():
            # Some installations use month names with a capital first letter.
            month = datetime.fromisoformat(trading_date).strftime("%B")
            alt = self.root / datetime.fromisoformat(trading_date).strftime("%Y") / month / trading_date
            day = alt if alt.exists() else day
        if not day.exists():
            return []
        return sorted(
            p for p in day.iterdir()
            if p.is_file() and p.suffix.lower() in {".xlsx", ".xls", ".csv"}
        )

    def read_file(self, path: str | Path, trading_date: str) -> list[PECERecord]:
        path = Path(path)
        created = datetime.fromtimestamp(path.stat().st_ctime)
        if path.suffix.lower() == ".csv":
            frame = pd.read_csv(path)
        else:
            frame = pd.read_excel(path, sheet_name=0)

        symbol_col = _find_column(frame.columns, ("Symbol",))
        time_col = _find_column(frame.columns, ("Time",))
        snapshot_col = _find_column(frame.columns, ("Snapshot", "Snapshot Time", "SnapshotTime"))
        chg_col = _find_column(frame.columns, ("Diff(PE-CE OI Chg)", "Diff (PE-CE OI Chg)"))
        pct_col = _find_column(frame.columns, ("Diff(PE-CE OI Chg %)", "Diff (PE-CE OI Chg %)"))

        if not symbol_col or not pct_col:
            return []

        records: list[PECERecord] = []
        for _, row in frame.iterrows():
            symbol = str(row.get(symbol_col, "")).strip().upper()
            if not symbol:
                continue
            observation = _parse_ts(row.get(time_col), trading_date)
            snapshot = _parse_ts(row.get(snapshot_col), trading_date) if snapshot_col else None

            def num(col):
                if not col:
                    return None
                try:
                    value = pd.to_numeric(row.get(col), errors="coerce")
                    return None if pd.isna(value) else float(value)
                except Exception:
                    return None

            raw = {str(k): row.get(k) for k in frame.columns}
            records.append(
                PECERecord(
                    trading_date=trading_date,
                    symbol=symbol,
                    observation_time=observation,
                    snapshot_time=snapshot,
                    pece_oi_chg=num(chg_col),
                    pece_oi_chg_pct=num(pct_col),
                    source_file=str(path),
                    file_created_time=created,
                    raw=raw,
                )
            )
        return records

    def load_records(self, trading_date: str) -> list[PECERecord]:
        records = []
        for path in self.discover(trading_date):
            records.extend(self.read_file(path, trading_date))
        return records
