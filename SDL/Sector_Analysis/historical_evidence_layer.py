from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# NTIS SDL - consolidated historical evidence layer
# Research-only. Does not modify production SDL logic.
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve()
SDL_ROOT = HERE.parents[1]
DATA_ROOT = SDL_ROOT / "data"
INTEL_ROOT = SDL_ROOT / "Sector_Analysis" / ".sector_intelligence"
CANONICAL = INTEL_ROOT / "straddle_historical_research" / "canonical_observations.csv"
EVENT_ROOT = DATA_ROOT / "output" / "tradable_events"
OUT_ROOT = INTEL_ROOT / "historical_evidence"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

EVENT_FILES = (
    EVENT_ROOT / "approaching_breakouts.csv",
    EVENT_ROOT / "breakout_events.csv",
)

CHUNK_SIZE = 75_000
PRE_EVENT_MINUTES = 30
MAX_OBSERVATIONS_PER_EVENT = 20

SYMBOL_ALIASES = ("symbol", "stock", "ticker", "ticker_symbol", "scrip", "security")
TS_ALIASES = (
    "timestamp", "observation_timestamp", "datetime",
    "observation_datetime", "observation_time"
)
DATE_ALIASES = ("trading_date", "trade_date", "date")
SOURCE_ALIASES = ("source_file", "source", "report_type", "report")

EVIDENCE_ALIASES = {
    "price": ("price", "close", "cmp", "current_price"),
    "price_chg_pct": ("price_chg_pct", "price_change_pct", "price_chg_percent", "price_change_percent"),
    "oi_chg_pct": ("oi_chg_pct", "oi_change_pct", "oi_chg_percent"),
    "volume_chg_pct": ("volume_chg_pct", "volume_change_pct", "volume_chg_percent"),
    "iv_chg_pct": ("iv_chg_pct", "iv_change_pct", "iv_chg_percent"),
    "pcr_chg_pct": ("pcr_chg_pct", "pcr_change_pct"),
    "ce_oi": ("ce_oi", "tot_ce_oi_chg", "tol_ce_oi_chg"),
    "pe_oi": ("pe_oi", "tot_pe_oi_chg", "tol_pe_oi_chg"),
    "pe_ce": ("pe_ce", "tot_pe_ce_oi_chg", "tol_pe_ce_oi_chg"),
    "buildup": ("buildup", "build_up"),
    "atm_straddle_pct": ("atm_straddle_pct", "atm_straddle_percent"),
}


def norm_col(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def pick_column(columns, aliases):
    mapping = {norm_col(c): c for c in columns}
    for alias in aliases:
        if alias in mapping:
            return mapping[alias]
    return None


def norm_symbol(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value).strip().upper())


def parse_one(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    s = str(value).strip()
    if not s or s.lower() in {"nan", "nat", "none", "null"}:
        return pd.NaT

    # Explicit formats first. This avoids locale-dependent inference.
    formats = (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M:%S.%f",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    )
    for fmt in formats:
        try:
            return pd.Timestamp.strptime(s, fmt)
        except Exception:
            pass
    try:
        return pd.Timestamp(s)
    except Exception:
        return pd.NaT


def parse_series(series: pd.Series) -> pd.Series:
    return pd.Series(
        [parse_one(v) for v in series],
        index=series.index,
        dtype="datetime64[ns]",
    )


def timestamp_from_source_name(value: object):
    """Recover timestamps from report filenames when canonical timestamp is absent."""
    if value is None or pd.isna(value):
        return pd.NaT
    s = str(value)

    # Examples seen in the permanent repository include:
    # ..._4_9_2026_144321.xlsx
    # ..._2026-08-11_143000.xlsx
    patterns = (
        (r"(?<!\d)(\d{1,2})_(\d{1,2})_(\d{4})_(\d{6})(?!\d)", "%d_%m_%Y_%H%M%S"),
        (r"(?<!\d)(\d{4})-(\d{2})-(\d{2})[_ ](\d{6})(?!\d)", "%Y-%m-%d_%H%M%S"),
        (r"(?<!\d)(\d{4})-(\d{2})-(\d{2})[_ ](\d{2})(\d{2})(\d{2})(?!\d)", "%Y-%m-%d_%H%M%S"),
        (r"(?<!\d)(\d{2})(\d{2})(\d{4})[_ ](\d{6})(?!\d)", "%d%m%Y_%H%M%S"),
    )
    for pattern, _fmt in patterns:
        m = re.search(pattern, s)
        if not m:
            continue
        try:
            if len(m.groups()) == 4 and "_" in pattern and pattern.startswith("(?<!\\d)(\\d{1,2})"):
                return pd.Timestamp(
                    year=int(m.group(3)), month=int(m.group(2)), day=int(m.group(1)),
                    hour=int(m.group(4)[:2]), minute=int(m.group(4)[2:4]), second=int(m.group(4)[4:6])
                )
            if len(m.groups()) == 4:
                return pd.Timestamp(
                    year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)),
                    hour=int(m.group(4)[:2]), minute=int(m.group(4)[2:4]), second=int(m.group(4)[4:6])
                )
        except Exception:
            continue
    return pd.NaT


def read_events():
    frames = []
    for path in EVENT_FILES:
        if not path.exists():
            continue
        df = pd.read_csv(path, low_memory=False)
        sym_col = pick_column(df.columns, SYMBOL_ALIASES)
        ts_col = pick_column(df.columns, TS_ALIASES)
        if not sym_col or not ts_col:
            continue

        x = pd.DataFrame({
            "symbol": df[sym_col].map(norm_symbol),
            "event_ts": parse_series(df[ts_col]),
            "event_source": path.name,
        })
        for col in ("event_id", "direction", "status"):
            x[col] = df[col].astype(str) if col in df.columns else ""

        x = x[(x["symbol"] != "") & x["event_ts"].notna()].copy()
        x["event_date"] = x["event_ts"].dt.date
        frames.append(x)

    if not frames:
        raise RuntimeError("No usable SDL event files were found.")

    events = pd.concat(frames, ignore_index=True)

    # If event_id exists, use it as the stable identity. Otherwise use source,
    # symbol and timestamp. Do not silently merge distinct events.
    event_ids = events["event_id"].str.strip()
    if event_ids.ne("").any():
        events["_event_key"] = event_ids.where(
            event_ids.ne(""),
            events["symbol"] + "|" + events["event_ts"].astype(str) + "|" + events["event_source"]
        )
    else:
        events["_event_key"] = (
            events["symbol"] + "|" + events["event_ts"].astype(str) + "|" + events["event_source"]
        )

    events = events.drop_duplicates("_event_key").reset_index(drop=True)
    return events


def main():
    print("NTIS SDL — CONSOLIDATED HISTORICAL EVIDENCE LAYER")
    print(f"CANONICAL: {CANONICAL}")
    print(f"EVENT ROOT: {EVENT_ROOT}")

    if not CANONICAL.exists():
        raise FileNotFoundError(CANONICAL)

    events = read_events()
    print(f"EVENTS: {len(events)} | SYMBOLS: {events.symbol.nunique()} | DATES: {events.event_date.nunique()}")

    header = pd.read_csv(CANONICAL, nrows=0)
    symbol_col = pick_column(header.columns, SYMBOL_ALIASES)
    ts_col = pick_column(header.columns, TS_ALIASES)
    source_col = pick_column(header.columns, SOURCE_ALIASES)

    if not symbol_col:
        raise RuntimeError("Canonical file has no recognizable symbol field.")

    # We deliberately do not trust the canonical date field after reconciliation.
    # Timestamp is primary; source filename is a research fallback.
    use = [symbol_col]
    if ts_col:
        use.append(ts_col)
    if source_col:
        use.append(source_col)
    for aliases in EVIDENCE_ALIASES.values():
        c = pick_column(header.columns, aliases)
        if c:
            use.append(c)
    use = list(dict.fromkeys(use))
    rename = {symbol_col: "symbol"}
    if ts_col:
        rename[ts_col] = "canonical_ts"
    if source_col:
        rename[source_col] = "source_file"
    for name, aliases in EVIDENCE_ALIASES.items():
        c = pick_column(header.columns, aliases)
        if c:
            rename[c] = name

    needed_symbols = set(events.symbol)

    # Index events by symbol/date for fast lookup.
    events_by_key = defaultdict(list)
    for row in events.itertuples(index=False):
        events_by_key[(row.symbol, row.event_date)].append(row)

    # Accumulate only event-aligned rows. The canonical file is never fully
    # loaded into memory.
    parts = []
    counts = Counter()
    chunks = 0

    for raw in pd.read_csv(CANONICAL, usecols=use, chunksize=CHUNK_SIZE, low_memory=False):
        chunks += 1
        chunk = raw.rename(columns=rename)
        chunk["symbol"] = chunk["symbol"].map(norm_symbol)
        chunk = chunk[chunk["symbol"].isin(needed_symbols)].copy()
        counts["symbol_rows"] += len(chunk)
        if chunk.empty:
            continue

        # Primary timestamp.
        if "canonical_ts" in chunk.columns:
            chunk["obs_ts"] = parse_series(chunk["canonical_ts"])
        else:
            chunk["obs_ts"] = pd.NaT

        # Fallback: recover report timestamp from source filename.
        if "source_file" in chunk.columns:
            missing = chunk["obs_ts"].isna()
            if missing.any():
                chunk.loc[missing, "obs_ts"] = [
                    timestamp_from_source_name(v) for v in chunk.loc[missing, "source_file"]
                ]
                counts["timestamp_filename_recovered"] += int(missing.sum())

        counts["timestamp_rows"] += int(chunk["obs_ts"].notna().sum())
        chunk = chunk[chunk["obs_ts"].notna()].copy()
        if chunk.empty:
            continue

        chunk["obs_date"] = chunk["obs_ts"].dt.date

        # Only dates that actually occur in SDL events.
        valid_dates = set(events.event_date)
        chunk = chunk[chunk["obs_date"].isin(valid_dates)]
        if chunk.empty:
            continue

        # Grouping within the chunk avoids repeatedly filtering the entire chunk.
        for (symbol, obs_date), sub in chunk.groupby(["symbol", "obs_date"], sort=False):
            evs = events_by_key.get((symbol, obs_date), ())
            if not evs:
                continue

            for ev in evs:
                lo = ev.event_ts - pd.Timedelta(minutes=PRE_EVENT_MINUTES)
                hit = sub[(sub["obs_ts"] < ev.event_ts) & (sub["obs_ts"] >= lo)].copy()
                if hit.empty:
                    continue

                # itertuples() may rename underscore-prefixed fields;
                # use the original event index to retrieve values safely.
                ev_key = events.loc[ev.Index, "_event_key"] if hasattr(ev, "Index") else ""
                hit["event_key"] = ev_key
                hit["event_id"] = ev.event_id
                hit["event_ts"] = ev.event_ts
                hit["event_direction"] = ev.direction
                hit["event_status"] = ev.status
                hit["event_source"] = ev.event_source
                hit["minutes_before_event"] = (
                    (ev.event_ts - hit["obs_ts"]).dt.total_seconds() / 60.0
                )
                parts.append(hit)
                counts["candidate_trace_rows"] += len(hit)

        if chunks % 10 == 0:
            print(
                f"CHUNKS: {chunks} | SYMBOL ROWS: {counts['symbol_rows']} | "
                f"TIMESTAMP ROWS: {counts['timestamp_rows']} | "
                f"TRACE CANDIDATES: {counts['candidate_trace_rows']}"
            )

    if parts:
        trace = pd.concat(parts, ignore_index=True)
    else:
        trace = pd.DataFrame()

    if not trace.empty:
        # Same symbol/timestamp/source can occur in multiple report rows. Preserve
        # provenance, but don't count exact duplicate evidence twice.
        dedup_cols = ["event_key", "symbol", "obs_ts"]
        if "source_file" in trace.columns:
            dedup_cols.append("source_file")
        trace = trace.drop_duplicates(dedup_cols, keep="first")

        # Keep the closest observations to the event, bounded per event.
        trace = trace.sort_values(["event_key", "obs_ts"])
        trace = (
            trace.groupby("event_key", group_keys=False)
            .tail(MAX_OBSERVATIONS_PER_EVENT)
            .sort_values(["event_key", "obs_ts"])
        )

    trace_path = OUT_ROOT / "event_aligned_evidence.csv"
    trace.to_csv(trace_path, index=False)

    # Compact event-level coverage.
    if not trace.empty:
        rows = []
        for key, g in trace.groupby("event_key", sort=False):
            rows.append({
                "event_key": key,
                "event_id": g["event_id"].iloc[0],
                "symbol": g["symbol"].iloc[0],
                "event_ts": g["event_ts"].iloc[0],
                "direction": g["event_direction"].iloc[0],
                "status": g["event_status"].iloc[0],
                "evidence_rows": len(g),
                "first_evidence_ts": g["obs_ts"].min(),
                "last_evidence_ts": g["obs_ts"].max(),
                "source_count": g["source_file"].nunique() if "source_file" in g.columns else 0,
                "closest_evidence_minutes": float(g["minutes_before_event"].min()),
            })
        event_summary = pd.DataFrame(rows)
    else:
        event_summary = pd.DataFrame(columns=[
            "event_key", "event_id", "symbol", "event_ts", "direction", "status",
            "evidence_rows", "first_evidence_ts", "last_evidence_ts",
            "source_count", "closest_evidence_minutes"
        ])

    event_summary.to_csv(OUT_ROOT / "event_evidence_summary.csv", index=False)

    coverage = {
        "events_total": len(events),
        "events_with_trace": int(event_summary["event_key"].nunique()) if not event_summary.empty else 0,
        "trace_coverage_pct": round(
            100 * (event_summary["event_key"].nunique() / len(events)), 2
        ) if len(events) else 0,
        "trace_rows": len(trace),
        "canonical_chunks": chunks,
        "symbol_matching_rows": counts["symbol_rows"],
        "parseable_observation_timestamps": counts["timestamp_rows"],
        "filename_timestamp_recoveries": counts["timestamp_filename_recovered"],
        "pre_event_window_minutes": PRE_EVENT_MINUTES,
        "max_observations_per_event": MAX_OBSERVATIONS_PER_EVENT,
        "decision": "HISTORICAL_PATTERN_DISCOVERY_READY" if not event_summary.empty else "INSUFFICIENT_EVENT_ALIGNMENT",
    }
    (OUT_ROOT / "historical_evidence_summary.json").write_text(
        json.dumps(coverage, indent=2, default=str), encoding="utf-8"
    )

    print("HISTORICAL EVIDENCE BUILD COMPLETE")
    print(f"CANONICAL CHUNKS: {chunks}")
    print(f"SYMBOL-MATCHING ROWS: {counts['symbol_rows']}")
    print(f"PARSEABLE / RECOVERED TIMESTAMP ROWS: {counts['timestamp_rows']}")
    print(f"TRACE ROWS: {len(trace)}")
    print(f"EVENTS WITH TRACE: {coverage['events_with_trace']} / {len(events)}")
    print(f"OUTPUT: {OUT_ROOT}")
    print(f"DECISION: {coverage['decision']}")


if __name__ == "__main__":
    main()
