from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
SDL_ROOT = HERE.parents[1]
DATA_ROOT = SDL_ROOT / "data"
RESEARCH_ROOT = SDL_ROOT / "Sector_Analysis" / ".sector_intelligence"
CANONICAL = RESEARCH_ROOT / "straddle_historical_research" / "canonical_observations.csv"
EVENT_ROOT = DATA_ROOT / "output" / "tradable_events"
OUT_ROOT = RESEARCH_ROOT / "historical_traceback"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

EVENT_FILES = [
    EVENT_ROOT / "approaching_breakouts.csv",
    EVENT_ROOT / "breakout_events.csv",
]

SYMBOL_KEYS = {"symbol", "stock", "ticker", "ticker_symbol", "scrip", "security"}
TS_KEYS = {"timestamp", "observation_timestamp", "datetime", "observation_datetime", "observation_time"}
DATE_KEYS = {"trading_date", "trade_date", "date"}

# Canonical evidence is deliberately treated as research input only.
# These are aliases for fields already observed in the reconstruction schema.
FIELD_ALIASES = {
    "price": ["price", "close", "cmp", "current_price", "price_chg", "price_chg_pct"],
    "price_chg_pct": ["price_chg_pct", "price_change_pct", "price_chg_percent", "price_change_percent"],
    "oi_chg_pct": ["oi_chg_pct", "oi_change_pct", "oi_chg_percent"],
    "volume_chg_pct": ["volume_chg_pct", "volume_change_pct", "volume_chg_percent"],
    "iv_chg_pct": ["iv_chg_pct", "iv_change_pct", "iv_chg_percent"],
    "pcr_chg_pct": ["pcr_chg_pct", "pcr_change_pct"],
    "ce_oi": ["ce_oi", "tot_ce_oi_chg", "tol_ce_oi_chg"],
    "pe_oi": ["pe_oi", "tot_pe_oi_chg", "tol_pe_oi_chg"],
    "pe_ce": ["pe_ce", "tot_pe_ce_oi_chg", "tol_pe_ce_oi_chg"],
    "buildup": ["buildup", "build_up"],
    "atm_straddle_pct": ["atm_straddle_pct", "atm_straddle_percent"],
    "source": ["source_file", "source", "report_type", "report"],
}

def norm_col(x):
    return re.sub(r"[^a-z0-9]+", "_", str(x).strip().lower()).strip("_")

def pick(columns, candidates):
    by_norm = {norm_col(c): c for c in columns}
    for c in candidates:
        if c in by_norm:
            return by_norm[c]
    return None

def pick_alias(columns, names):
    by_norm = {norm_col(c): c for c in columns}
    for name in names:
        if name in by_norm:
            return by_norm[name]
    return None

def norm_symbol(x):
    if x is None or pd.isna(x):
        return ""
    return re.sub(r"\s+", "", str(x).strip().upper())

def parse_one(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    s = str(x).strip()
    if not s or s.lower() in {"nan", "nat", "none", "null"}:
        return pd.NaT
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S.%f", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    ):
        try:
            return pd.Timestamp.strptime(s, fmt)
        except Exception:
            pass
    try:
        return pd.Timestamp(s)
    except Exception:
        return pd.NaT

def parse_series(s):
    return pd.Series([parse_one(v) for v in s], index=s.index, dtype="datetime64[ns]")

def read_events():
    frames = []
    for path in EVENT_FILES:
        if not path.exists():
            continue
        df = pd.read_csv(path, low_memory=False)
        sym = pick(df.columns, SYMBOL_KEYS)
        ts = pick(df.columns, TS_KEYS)
        dt = pick(df.columns, DATE_KEYS)
        if not sym or not ts:
            continue
        x = pd.DataFrame({
            "symbol": df[sym].map(norm_symbol),
            "event_ts": parse_series(df[ts]),
            "event_source": path.name,
        })
        # Date is used only as fallback metadata; chronology is based on event_ts.
        if dt:
            x["event_date_raw"] = df[dt].astype(str)
        else:
            x["event_date_raw"] = ""
        for c in ("direction", "status", "event_id", "breakout_distance", "price_chg_pct"):
            if c in df.columns:
                x[c] = df[c]
            else:
                x[c] = ""
        frames.append(x)
    if not frames:
        raise RuntimeError("No usable SDL event file found.")
    e = pd.concat(frames, ignore_index=True)
    e = e[(e["symbol"] != "") & e["event_ts"].notna()].copy()
    e["event_date"] = e["event_ts"].dt.date
    # Same event may appear in more than one event file; preserve source but avoid
    # duplicate event identities when event_id exists.
    if "event_id" in e.columns and e["event_id"].astype(str).str.strip().ne("").any():
        e["_dedup_key"] = e["event_id"].astype(str)
    else:
        e["_dedup_key"] = (
            e["symbol"].astype(str) + "|" +
            e["event_ts"].astype(str) + "|" +
            e["event_source"].astype(str)
        )
    e = e.drop_duplicates("_dedup_key").reset_index(drop=True)
    return e

def main():
    print("SMART HISTORICAL TRACEBACK / FOOTPRINT DISCOVERY")
    print(f"CANONICAL: {CANONICAL}")
    print(f"EVENT ROOT: {EVENT_ROOT}")

    if not CANONICAL.exists():
        raise FileNotFoundError(CANONICAL)

    events = read_events()
    print(f"EVENTS: {len(events)} | SYMBOLS: {events.symbol.nunique()} | DATES: {events.event_date.nunique()}")

    header = pd.read_csv(CANONICAL, nrows=0)
    c_sym = pick(header.columns, SYMBOL_KEYS)
    c_ts = pick(header.columns, TS_KEYS)
    c_date = pick(header.columns, {"date", "trading_date", "trade_date"})
    if not c_sym or not c_ts:
        raise RuntimeError("Canonical dataset lacks symbol/timestamp fields.")

    # Only fields needed for traceback are read. Everything is chunked.
    chosen = {"symbol": c_sym, "timestamp": c_ts}
    for canon, aliases in FIELD_ALIASES.items():
        c = pick_alias(header.columns, aliases)
        if c and canon not in chosen:
            chosen[canon] = c

    usecols = list(dict.fromkeys(chosen.values()))
    rename = {v: k for k, v in chosen.items()}
    needed_symbols = set(events.symbol)
    event_by_key = defaultdict(list)
    for r in events.itertuples(index=False):
        event_by_key[(r.symbol, r.event_date)].append(r)

    # Keep only canonical rows on event symbol + timestamp-derived event date.
    # This avoids trusting the canonical "date" column, which reconciliation showed
    # collapses to one value.
    trace_parts = []
    counters = Counter()
    chunks = 0

    for chunk in pd.read_csv(CANONICAL, usecols=usecols, chunksize=75000, low_memory=False):
        chunks += 1
        chunk = chunk.rename(columns=rename)
        chunk["symbol"] = chunk["symbol"].map(norm_symbol)
        mask = chunk["symbol"].isin(needed_symbols)
        if not mask.any():
            continue
        chunk = chunk.loc[mask].copy()
        counters["symbol_rows"] += len(chunk)
        chunk["timestamp"] = parse_series(chunk["timestamp"])
        chunk = chunk[chunk["timestamp"].notna()].copy()
        counters["timestamp_rows"] += len(chunk)
        if chunk.empty:
            continue
        chunk["event_date"] = chunk["timestamp"].dt.date
        matched = 0
        rows = []
        for (sym, d), evs in event_by_key.items():
            sub = chunk[(chunk["symbol"] == sym) & (chunk["event_date"] == d)]
            if sub.empty:
                continue
            for ev in evs:
                # Strict chronology-safe window: evidence must precede event.
                lo = ev.event_ts - pd.Timedelta(minutes=30)
                hit = sub[(sub["timestamp"] < ev.event_ts) & (sub["timestamp"] >= lo)].copy()
                if hit.empty:
                    continue
                matched += len(hit)
                hit["event_id"] = str(getattr(ev, "event_id", "")) if hasattr(ev, "event_id") else ""
                hit["event_ts"] = ev.event_ts
                hit["event_source"] = ev.event_source
                hit["event_date"] = ev.event_date
                hit["direction"] = getattr(ev, "direction", "")
                hit["status"] = getattr(ev, "status", "")
                rows.append(hit)
        if rows:
            trace_parts.append(pd.concat(rows, ignore_index=True))
            counters["trace_rows"] += matched
        if chunks % 10 == 0:
            print(f"CHUNKS: {chunks} | SYMBOL ROWS: {counters['symbol_rows']} | TRACE ROWS: {counters['trace_rows']}")

    if trace_parts:
        trace = pd.concat(trace_parts, ignore_index=True)
        # Same source observation can be encountered against multiple event records.
        trace = trace.drop_duplicates(
            subset=["event_id", "symbol", "timestamp", "event_source"],
            keep="first"
        )
    else:
        trace = pd.DataFrame()

    trace_path = OUT_ROOT / "event_trace.csv"
    trace.to_csv(trace_path, index=False)

    # Build compact event-level sequence signatures without inventing scores.
    # A sequence is represented by observation count and available evidence fields.
    event_rows = []
    if not trace.empty:
        value_fields = [x for x in FIELD_ALIASES if x in trace.columns]
        for eid, g in trace.groupby("event_id", sort=False):
            g = g.sort_values("timestamp")
            row = {
                "event_id": eid,
                "symbol": g["symbol"].iloc[0],
                "event_ts": g["event_ts"].iloc[0],
                "direction": g["direction"].iloc[0],
                "status": g["status"].iloc[0],
                "observations": len(g),
                "first_evidence_ts": g["timestamp"].min(),
                "last_evidence_ts": g["timestamp"].max(),
            }
            for f in value_fields:
                row[f"{f}_observed"] = int(g[f].notna().sum())
            event_rows.append(row)

    summary = pd.DataFrame(event_rows)
    summary.to_csv(OUT_ROOT / "event_trace_summary.csv", index=False)

    # Cross-event footprint availability, not a fabricated predictive rate.
    footprint = []
    if not summary.empty:
        for f in [x for x in FIELD_ALIASES if f in summary.columns]:
            col = f"{f}_observed"
            if col in summary:
                footprint.append({
                    "field": f,
                    "events_with_evidence": int((summary[col] > 0).sum()),
                    "events_total": len(summary),
                    "coverage_pct": round(100 * (summary[col] > 0).mean(), 2),
                })
    pd.DataFrame(footprint).to_csv(OUT_ROOT / "footprint_coverage.csv", index=False)

    result = {
        "events": len(events),
        "event_symbols": int(events.symbol.nunique()),
        "event_dates": int(events.event_date.nunique()),
        "canonical_chunks": chunks,
        "symbol_matching_rows": counters["symbol_rows"],
        "timestamp_parseable_matching_rows": counters["timestamp_rows"],
        "trace_rows": int(len(trace)),
        "trace_events": int(summary["event_id"].nunique()) if not summary.empty else 0,
        "trace_output": str(trace_path),
        "decision": "PATTERN_DISCOVERY_READY" if not summary.empty else "NO_CHRONOLOGY_SAFE_TRACE",
        "window_minutes": 30,
    }
    (OUT_ROOT / "traceback_summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print("TRACEBACK COMPLETE")
    print(f"CANONICAL CHUNKS: {chunks}")
    print(f"SYMBOL-MATCHING ROWS: {counters['symbol_rows']}")
    print(f"PARSEABLE TIMESTAMP ROWS: {counters['timestamp_rows']}")
    print(f"TRACE ROWS: {len(trace)}")
    print(f"TRACE EVENTS: {summary['event_id'].nunique() if not summary.empty else 0}")
    print(f"OUTPUT: {OUT_ROOT}")
    print(f"DECISION: {result['decision']}")

if __name__ == "__main__":
    main()
