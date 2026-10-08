from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

import openpyxl

PREFIX = "Daywise_Price_and_OI_Summary_"
TS_RE = re.compile(r"_(\d{8})_(\d{6})\.xlsx$", re.I)

PECE_PREFIX = "PECE_"
PECE_REQUIRED = "Diff(PE-CE OI Chg %)"


def source_root() -> Path:
    return Path(os.environ.get(
        "NTIS_W73_SOURCE_ROOT",
        r"D:\My-data\Share_P&L\Ichart Data\Screenshot",
    ))


def pece_root() -> Path:
    return Path(os.environ.get(
        "NTIS_W73_PECE_SOURCE_ROOT",
        r"D:\My-data\Share_P&L\Ichart Data\Screenshot\PECE_Volume",
    ))


def discover_day_folder(trading_date: str, month="September26") -> Path:
    return source_root() / month / trading_date


def discover_pece_folder(trading_date: str) -> Path:
    dt = datetime.strptime(trading_date, "%Y-%m-%d")
    return pece_root() / str(dt.year) / dt.strftime("%B").lower() / trading_date


def timestamp_from_name(name: str) -> datetime | None:
    m = TS_RE.search(name)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")


def file_created_at(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_ctime)


def discover_files(
    trading_date: str,
    month="September26",
    cutoff: datetime | None = None,
) -> list[tuple[Path, datetime]]:
    folder = discover_day_folder(trading_date, month)
    if not folder.exists():
        return []

    out = []
    for p in folder.iterdir():
        if not p.is_file() or p.suffix.lower() != ".xlsx" or not p.name.startswith(PREFIX):
            continue
        ts = timestamp_from_name(p.name)
        if ts is not None and (cutoff is None or ts <= cutoff):
            out.append((p, ts))
    return sorted(out, key=lambda x: x[1])


def discover_pece_files(trading_date: str) -> list[Path]:
    folder = discover_pece_folder(trading_date)
    if not folder.exists():
        return []
    return sorted(
        [
            p for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() == ".xlsx"
            and p.name.startswith(PECE_PREFIX)
        ],
        key=file_created_at,
    )


def read_pece_file(path: Path) -> dict[str, list[dict]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            return {}

        header = [str(x).strip() if x is not None else "" for x in header]
        idx = {name: i for i, name in enumerate(header) if name}

        symbol_i = idx.get("Symbol")
        pece_i = idx.get(PECE_REQUIRED)
        if symbol_i is None or pece_i is None:
            return {}

        direct_num_i = idx.get("Diff(PE-CE OI Chg)")
        time_i = idx.get("Time")
        snapshot_i = idx.get("Snapshot")

        result = {}
        for values in rows:
            if symbol_i >= len(values):
                continue
            symbol = str(values[symbol_i] or "").strip().upper()
            if not symbol:
                continue

            row = {
                "value": values[pece_i] if pece_i < len(values) else None,
                "diff": values[direct_num_i] if direct_num_i is not None and direct_num_i < len(values) else None,
                "time": values[time_i] if time_i is not None and time_i < len(values) else None,
                "snapshot": values[snapshot_i] if snapshot_i is not None and snapshot_i < len(values) else None,
            }
            result.setdefault(symbol, []).append(row)

        return result
    finally:
        wb.close()


def build_pece_index(trading_date: str) -> list[tuple[datetime, Path, dict[str, list[dict]]]]:
    result = []
    for path in discover_pece_files(trading_date):
        try:
            created = file_created_at(path)
            rows = read_pece_file(path)
            if rows:
                result.append((created, path, rows))
        except Exception:
            continue
    return result


def nearest_pece(
    authoritative_created: datetime,
    symbol: str,
    pece_index: list[tuple[datetime, Path, dict[str, list[dict]]]],
    leader_observation: datetime | None = None,
) -> tuple[datetime, Path, dict] | None:
    symbol = symbol.strip().upper()
    leader = leader_observation or authoritative_created

    available_files = [
        (created, path, rows[symbol])
        for created, path, rows in pece_index
        if symbol in rows and created <= authoritative_created
    ]
    if not available_files:
        return None

    usable = []
    for pece_created, pece_path, observations in available_files:
        for row in observations:
            value = row.get("time")
            if value is None:
                continue
            try:
                if hasattr(value, "hour"):
                    obs = leader.replace(
                        hour=value.hour,
                        minute=value.minute,
                        second=getattr(value, "second", 0),
                        microsecond=0,
                    )
                else:
                    m = re.search(
                        r"(\d{1,2}):(\d{2})(?::(\d{2}))?",
                        str(value),
                    )
                    if not m:
                        continue
                    obs = leader.replace(
                        hour=int(m.group(1)),
                        minute=int(m.group(2)),
                        second=int(m.group(3) or 0),
                        microsecond=0,
                    )
                if obs <= leader:
                    usable.append((obs, pece_created, pece_path, row))
            except Exception:
                continue

    if not usable:
        return None

    _, pece_created, pece_path, selected = max(
        usable,
        key=lambda x: x[0],
    )
    return pece_created, pece_path, selected


def read_workbook(
    path: Path,
    ts: datetime,
    pece_index: list[tuple[datetime, Path, dict[str, list[dict]]]] | None = None,
) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            return []

        header = [str(x).strip() if x is not None else "" for x in header]
        result = []
        authoritative_created = file_created_at(path)

        for vals in rows:
            r = {
                header[i]: (vals[i] if i < len(vals) else None)
                for i in range(len(header))
                if header[i]
            }
            sym = str(r.get("Symbol", "")).strip()
            if not sym:
                continue

            r["_trading_date"] = ts.strftime("%Y-%m-%d")
            r["_observation_timestamp"] = ts.isoformat(timespec="seconds")
            r["_source_file"] = path.name
            r["_authoritative_file_created_time"] = authoritative_created.isoformat(
                timespec="seconds"
            )
            r["family"] = "FUTURES"

            # Daywise-led supporting-stream alignment:
            # only PECE files available by the Daywise leader file time are
            # eligible; then latest PECE observation <= the Daywise observation.
            # Timestamp equality is not required. No reconstruction of PE-CE percentage.
            if pece_index:
                match = nearest_pece(authoritative_created, sym, pece_index, leader_observation=ts)
                if match:
                    pece_created, pece_path, pece = match
                    if r.get("Tot PE-CE OI Chg") in (None, "", "-"):
                        r["Tot PE-CE OI Chg"] = pece.get("diff")
                    r["Tot PE-CE OI Chg %"] = pece.get("value")
                    r["_pece_source_file"] = pece_path.name
                    r["_pece_file_created_time"] = pece_created.isoformat(
                        timespec="seconds"
                    )
                    r["_pece_match_delta_seconds"] = round(
                        abs((pece_created - authoritative_created).total_seconds()), 3
                    )
                    r["_pece_time"] = pece.get("time")
                    r["_pece_snapshot"] = pece.get("snapshot")
                    r["_pece_match_status"] = "MATCHED"
                else:
                    r["_pece_match_status"] = "MISSING"
            else:
                r["_pece_match_status"] = "SOURCE_UNAVAILABLE"

            result.append(r)

        return result
    finally:
        wb.close()


def ingest(
    trading_date: str,
    month="September26",
    cache_root: str | Path = "07_OUTPUT/live_cache",
) -> dict:
    cache = Path(cache_root)
    cache.mkdir(parents=True, exist_ok=True)

    state_path = cache / "ingest_state.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"files": {}}
    )

    pece_index = build_pece_index(trading_date)

    count = 0
    symbols = set()
    intervals = []
    matched_rows = 0

    for p, ts in discover_files(trading_date, month):
        key = p.name
        if key in state["files"]:
            continue

        try:
            rows = read_workbook(p, ts, pece_index)
        except Exception:
            continue

        out = cache / f"{trading_date}.jsonl"
        with out.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(
                    json.dumps(
                        r,
                        ensure_ascii=False,
                        default=str,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                count += 1
                symbols.add(r["Symbol"].strip().upper())
                if r.get("_pece_match_status") == "MATCHED":
                    matched_rows += 1

        state["files"][key] = {
            "timestamp": ts.isoformat(),
            "rows": len(rows),
            "authoritative_file_created_time": file_created_at(p).isoformat(
                timespec="seconds"
            ),
        }
        intervals.append(ts.isoformat())

    state_path.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )

    return {
        "status": "OK",
        "trading_date": trading_date,
        "new_rows": count,
        "new_symbols": len(symbols),
        "new_intervals": intervals,
        "pece_files_available": len(pece_index),
        "pece_rows_matched": matched_rows,
        "cache": str(cache / f"{trading_date}.jsonl"),
    }
