from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
SDL_ROOT = HERE.parents[1]
DATA_ROOT = SDL_ROOT / "data"
RESEARCH_ROOT = SDL_ROOT / "Sector_Analysis" / ".sector_intelligence"
CANONICAL = RESEARCH_ROOT / "straddle_historical_research" / "canonical_observations.csv"
EVENT_ROOT = DATA_ROOT / "output" / "tradable_events"
OUT_ROOT = RESEARCH_ROOT / "traceback_reconciliation"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

EVENT_FILES = [
    EVENT_ROOT / "approaching_breakouts.csv",
    EVENT_ROOT / "breakout_events.csv",
]

SYMBOL_KEYS = {"symbol", "stock", "ticker", "scrip", "security", "name"}
DATE_KEYS = {"trading_date", "trade_date", "date"}
TS_KEYS = {"observation_timestamp", "timestamp", "datetime", "observation_time", "time"}
SOURCE_KEYS = {"source_file", "source", "report_type", "report"}

def norm_col(x):
    return re.sub(r"[^a-z0-9]+", "_", str(x).strip().lower()).strip("_")

def pick_col(columns, keys):
    m = {norm_col(c): c for c in columns}
    for k in keys:
        if k in m:
            return m[k]
    for nk, orig in m.items():
        if any(nk == k or nk.endswith("_" + k) or k in nk for k in keys):
            return orig
    return None

def norm_symbol(x):
    if x is None or pd.isna(x):
        return ""
    s = str(x).strip().upper()
    s = re.sub(r"\s+", "", s)
    return s

def parse_one(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    s = str(x).strip()
    if not s or s.lower() in {"nan", "nat", "none", "null"}:
        return pd.NaT
    # Explicit common formats first; no day-first inference.
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M:%S.%f",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            pass
    # Handle ISO-like strings safely.
    try:
        return pd.Timestamp(s)
    except Exception:
        return pd.NaT

def parse_series(series):
    vals = [parse_one(v) for v in series]
    return pd.Series(vals, index=series.index, dtype="datetime64[ns]")

def inspect_event_file(path):
    if not path.exists():
        return pd.DataFrame(), {"file": str(path), "exists": False}
    df = pd.read_csv(path, low_memory=False)
    sym = pick_col(df.columns, SYMBOL_KEYS)
    dt = pick_col(df.columns, DATE_KEYS)
    ts = pick_col(df.columns, TS_KEYS)
    out = {
        "file": str(path),
        "exists": True,
        "rows": len(df),
        "columns": len(df.columns),
        "symbol_column": sym or "",
        "date_column": dt or "",
        "timestamp_column": ts or "",
        "timestamp_nonempty": int(df[ts].notna().sum()) if ts else 0,
    }
    if sym:
        df["_symbol_norm"] = df[sym].map(norm_symbol)
    else:
        df["_symbol_norm"] = ""
    if dt:
        df["_date_raw"] = df[dt]
        df["_date_norm"] = parse_series(df[dt]).dt.date
    else:
        df["_date_raw"] = ""
        df["_date_norm"] = pd.NaT
    if ts:
        df["_ts_raw"] = df[ts]
        df["_ts_norm"] = parse_series(df[ts])
    else:
        df["_ts_raw"] = ""
        df["_ts_norm"] = pd.NaT
    if "_ts_norm" in df:
        df["_event_date_from_ts"] = df["_ts_norm"].dt.date
    return df, out

def inspect_canonical():
    if not CANONICAL.exists():
        raise FileNotFoundError(CANONICAL)
    header = pd.read_csv(CANONICAL, nrows=0)
    sym = pick_col(header.columns, SYMBOL_KEYS)
    dt = pick_col(header.columns, DATE_KEYS)
    ts = pick_col(header.columns, TS_KEYS)
    src = pick_col(header.columns, SOURCE_KEYS)
    info = {
        "file": str(CANONICAL),
        "columns": len(header.columns),
        "symbol_column": sym or "",
        "date_column": dt or "",
        "timestamp_column": ts or "",
        "source_column": src or "",
        "columns_all": list(header.columns),
    }
    return info

def main():
    print("SMART HISTORICAL TRACEBACK RECONCILIATION")
    print(f"CANONICAL: {CANONICAL}")
    print(f"EVENT ROOT: {EVENT_ROOT}")

    cinfo = inspect_canonical()
    print(f"CANONICAL COLUMNS: {cinfo['columns']}")
    print(f"CANONICAL SYMBOL FIELD: {cinfo['symbol_column'] or 'NOT FOUND'}")
    print(f"CANONICAL DATE FIELD: {cinfo['date_column'] or 'NOT FOUND'}")
    print(f"CANONICAL TIMESTAMP FIELD: {cinfo['timestamp_column'] or 'NOT FOUND'}")

    event_frames = []
    event_infos = []
    for f in EVENT_FILES:
        df, inf = inspect_event_file(f)
        event_infos.append(inf)
        if not df.empty:
            df["_event_source_file"] = f.name
            event_frames.append(df)
        print(
            f"EVENT FILE: {f.name} | rows={inf.get('rows', 0)} | "
            f"symbol={inf.get('symbol_column','')} | date={inf.get('date_column','')} | "
            f"timestamp={inf.get('timestamp_column','')}"
        )

    events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    if events.empty:
        raise RuntimeError("No event rows found.")

    event_symbols = set(events.loc[events["_symbol_norm"] != "", "_symbol_norm"])
    event_dates = set(events["_date_norm"].dropna().tolist())
    event_ts = events["_ts_norm"].dropna()

    print(f"EVENT ROWS: {len(events)}")
    print(f"EVENT SYMBOLS: {len(event_symbols)}")
    print(f"EVENT DATES: {len(event_dates)}")
    print(f"EVENT PARSEABLE TIMESTAMPS: {len(event_ts)}")

    header = pd.read_csv(CANONICAL, nrows=0)
    csym = cinfo["symbol_column"]
    cdate = cinfo["date_column"]
    cts = cinfo["timestamp_column"]

    if not csym:
        raise RuntimeError("Canonical dataset has no recognizable symbol field.")
    if not cts and not cdate:
        raise RuntimeError("Canonical dataset has neither timestamp nor date field.")

    # Read only the fields needed for reconciliation.
    usecols = [x for x in [csym, cdate, cts, cinfo["source_column"]] if x]
    usecols = list(dict.fromkeys(usecols))

    stats = Counter()
    date_symbol_matches = Counter()
    candidate_rows = []
    canonical_symbols = set()
    canonical_dates = set()
    canonical_ts_count = 0

    # A small first pass is enough for coverage statistics; 75k-row chunks keep RAM bounded.
    for chunk_no, chunk in enumerate(pd.read_csv(CANONICAL, usecols=usecols, chunksize=75000, low_memory=False), 1):
        stats["chunks"] += 1
        chunk["_symbol_norm"] = chunk[csym].map(norm_symbol)
        canonical_symbols.update(x for x in chunk["_symbol_norm"].unique() if x)

        if cts:
            chunk["_ts_norm"] = parse_series(chunk[cts])
            chunk["_date_norm"] = chunk["_ts_norm"].dt.date
            canonical_ts_count += int(chunk["_ts_norm"].notna().sum())
        elif cdate:
            chunk["_ts_norm"] = pd.NaT
            chunk["_date_norm"] = parse_series(chunk[cdate]).dt.date

        canonical_dates.update(x for x in chunk["_date_norm"].dropna().unique())
        m = chunk["_symbol_norm"].isin(event_symbols)
        stats["symbol_matching_rows"] += int(m.sum())
        if cdate or cts:
            stats["date_matching_rows"] += int((m & chunk["_date_norm"].isin(event_dates)).sum())

        # Retain only a compact sample for detailed overlap diagnostics.
        if m.any():
            sub = chunk.loc[m, ["_symbol_norm", "_date_norm", "_ts_norm"]].copy()
            if cinfo["source_column"]:
                sub["_source"] = chunk.loc[m, cinfo["source_column"]].astype(str).to_numpy()
            candidate_rows.append(sub.head(2000))

    symbol_overlap = len(canonical_symbols & event_symbols)
    date_overlap = len(canonical_dates & event_dates)

    print(f"CANONICAL SYMBOLS: {len(canonical_symbols)}")
    print(f"SYMBOL OVERLAP: {symbol_overlap}")
    print(f"CANONICAL DATES: {len(canonical_dates)}")
    print(f"DATE OVERLAP: {date_overlap}")
    print(f"CANONICAL PARSEABLE TIMESTAMPS: {canonical_ts_count}")
    print(f"SYMBOL-MATCHING CANONICAL ROWS: {stats['symbol_matching_rows']}")
    print(f"DATE+SYMBOL CANDIDATE ROWS: {stats['date_matching_rows']}")

    candidates = pd.concat(candidate_rows, ignore_index=True) if candidate_rows else pd.DataFrame()
    if not candidates.empty:
        candidates.to_csv(OUT_ROOT / "candidate_observation_sample.csv", index=False)

    # Determine actual timestamp relationship using only matching symbol/date samples.
    # We deliberately do NOT infer a timestamp when it is absent.
    exact = before = after = 0
    deltas = []
    if not candidates.empty and cts and event_ts is not None:
        # Compact event index: symbol/date -> sorted timestamps.
        ev = events.loc[events["_symbol_norm"] != "", ["_symbol_norm", "_date_norm", "_ts_norm"]].dropna(subset=["_ts_norm"])
        ev = ev.drop_duplicates().sort_values(["_symbol_norm", "_date_norm", "_ts_norm"])
        by_key = defaultdict(list)
        for r in ev.itertuples(index=False, name=None):
            by_key[(r[0], r[1])].append(r[2])

        for r in candidates.itertuples(index=False, name=None):
            r_symbol, r_date, r_ts = r[0], r[1], r[2]
            if pd.isna(r_ts):
                continue
            arr = by_key.get((r_symbol, r_date))
            if not arr:
                continue
            # Find nearest event timestamp in the same symbol/date.
            nearest = min(arr, key=lambda t: abs(t - r_ts))
            delta = (r_ts - nearest).total_seconds()
            deltas.append(delta)
            if delta == 0:
                exact += 1
            elif delta < 0:
                before += 1
            else:
                after += 1

    rel = pd.DataFrame([{
        "exact_timestamp_rows": exact,
        "canonical_before_nearest_event_rows": before,
        "canonical_after_nearest_event_rows": after,
        "nearest_delta_min": min(deltas) / 60 if deltas else None,
        "nearest_delta_max": max(deltas) / 60 if deltas else None,
        "nearest_abs_delta_median_min": (pd.Series([abs(x) for x in deltas]).median() / 60) if deltas else None,
    }])
    rel.to_csv(OUT_ROOT / "timestamp_relationship.csv", index=False)

    report = {
        "canonical": cinfo,
        "event_files": event_infos,
        "event_rows": len(events),
        "event_symbols": len(event_symbols),
        "event_dates": len(event_dates),
        "event_parseable_timestamps": len(event_ts),
        "canonical_symbols": len(canonical_symbols),
        "symbol_overlap": symbol_overlap,
        "canonical_dates": len(canonical_dates),
        "date_overlap": date_overlap,
        "canonical_parseable_timestamps": canonical_ts_count,
        "symbol_matching_rows": stats["symbol_matching_rows"],
        "date_symbol_candidate_rows": stats["date_matching_rows"],
        "timestamp_relationship": rel.iloc[0].to_dict(),
        "decision": (
            "PROCEED_TO_TRACEBACK"
            if symbol_overlap and date_overlap and (before or exact)
            else "DIAGNOSE_SOURCE_ALIGNMENT_BEFORE_TRACEBACK"
        ),
    }
    (OUT_ROOT / "reconciliation_summary.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    print("RECONCILIATION COMPLETE")
    print(f"OUTPUT: {OUT_ROOT}")
    print(f"DECISION: {report['decision']}")

if __name__ == "__main__":
    main()
