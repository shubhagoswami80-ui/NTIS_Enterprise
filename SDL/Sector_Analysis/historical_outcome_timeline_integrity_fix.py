import argparse, json
from pathlib import Path
import pandas as pd
import numpy as np

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root = out.parent.parent
    candidates = list(root.rglob("canonical_strength_observations.csv"))
    if not candidates:
        raise SystemExit("CACHE_NOT_FOUND under .sector_intelligence")
    cache = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"CACHE_FOUND: {cache}")

    df = pd.read_csv(cache, low_memory=False)
    print(f"CACHE_ROWS: {len(df)}")

    # Normalize required columns without inventing data.
    rename = {}
    for c in df.columns:
        k = c.strip().lower().replace(" ", "_")
        if k in ("symbol",): rename[c] = "symbol"
        elif k in ("trade_date","trading_date","date"): rename[c] = "trade_date"
        elif k in ("timestamp","observation_timestamp","observed_at"): rename[c] = "timestamp"
        elif k in ("price_chg","price_change"): rename[c] = "price_chg"
        elif k in ("price_chg_pct","price_change_pct","price_chg_percent"): rename[c] = "price_chg_pct"
        elif k == "open": rename[c] = "open"
        elif k == "high": rename[c] = "high"
        elif k == "low": rename[c] = "low"
        elif k == "close": rename[c] = "close"
    df = df.rename(columns=rename)

    required = ["symbol","trade_date","timestamp"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit("MISSING_REQUIRED_COLUMNS: " + ",".join(missing))

    df["symbol"] = df["symbol"].astype("string").str.strip().str.upper()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df[df["symbol"].notna() & df["trade_date"].notna() & df["timestamp"].notna()].copy()

    # Deterministic duplicate resolution:
    # prefer rows with complete OHLC, then rows with price change, then stable source order.
    for c in ["open","high","low","close","price_chg","price_chg_pct"]:
        if c not in df.columns:
            df[c] = np.nan
    df["_ohlc_complete"] = df[["open","high","low","close"]].notna().all(axis=1).astype(int)
    df["_price_complete"] = df["price_chg"].notna().astype(int)
    df["_source_order"] = np.arange(len(df))
    dup_mask = df.duplicated(["symbol","trade_date","timestamp"], keep=False)
    dup_groups = int(df.loc[dup_mask, ["symbol","trade_date","timestamp"]].drop_duplicates().shape[0])
    dup_rows = int(dup_mask.sum())

    clean = (
        df.sort_values(
            ["symbol","trade_date","timestamp","_ohlc_complete","_price_complete","_source_order"],
            ascending=[True,True,True,False,False,True],
            kind="mergesort"
        )
        .drop_duplicates(["symbol","trade_date","timestamp"], keep="first")
        .sort_values(["symbol","trade_date","timestamp"], kind="mergesort")
        .reset_index(drop=True)
    )
    clean.to_csv(out / "clean_intraday_timeline.csv", index=False)

    # Verify chronological future observation availability by observation index.
    groups = clean.groupby(["symbol","trade_date"], sort=False)
    records = []
    for (sym, day), g in groups:
        g = g.sort_values("timestamp")
        n = len(g)
        for i, (_, r) in enumerate(g.iterrows()):
            row = {
                "symbol": sym, "trade_date": day, "timestamp": r["timestamp"],
                "sequence_index": i, "sequence_length": n,
                "has_t1": i+1 < n, "has_t2": i+2 < n, "has_t3": i+3 < n,
                "has_t5": i+5 < n, "has_t10": i+10 < n, "has_t20": i+20 < n
            }
            records.append(row)
    horizons = pd.DataFrame(records)
    horizons.to_csv(out / "horizon_availability.csv", index=False)

    summary = {}
    for c in ["has_t1","has_t2","has_t3","has_t5","has_t10","has_t20"]:
        summary[c] = int(horizons[c].sum())

    result = {
        "status": "HISTORICAL_OUTCOME_TIMELINE_INTEGRITY_FIX_COMPLETE",
        "cache_rows": int(len(df)),
        "clean_timeline_rows": int(len(clean)),
        "duplicate_symbol_date_timestamp_groups_found": dup_groups,
        "duplicate_rows_found": dup_rows,
        "duplicates_removed": int(len(df)-len(clean)),
        "unique_symbol_date_pairs": int(clean.groupby(["symbol","trade_date"]).ngroups),
        "symbols": int(clean["symbol"].nunique()),
        "dates": int(clean["trade_date"].nunique()),
        "timestamped": int(clean["timestamp"].notna().sum()),
        "horizon_available_observations": summary,
        "output": str(out)
    }
    (out / "integrity_summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()
