from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import time
import pandas as pd

DEFAULT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
CACHE_DIR_NAME = ".sector_intelligence"
DISCOVERY_NAME = "smart_replay_hit_discovery"
EVIDENCE_CANDIDATES = [
    "canonical_strength_observations.csv",
    "canonical_observations.csv",
]
OUT_NAME = "time_maturity_persistence_study_v3"

CUTOFFS = {"09:30": time(9,30), "09:45": time(9,45), "10:00": time(10,0), "10:15": time(10,15)}

def parse_args():
    p = argparse.ArgumentParser(description="Timestamp-aware cache-only maturity study.")
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    p.add_argument("--min-rows", type=int, default=20)
    return p.parse_args()

def pick_cache(root: Path):
    cache = root / CACHE_DIR_NAME
    candidates = [cache / DISCOVERY_NAME / x for x in EVIDENCE_CANDIDATES]
    # Also check the broader sector intelligence tree without scanning raw files.
    candidates += list(cache.rglob("canonical_strength_observations.csv"))
    candidates += list(cache.rglob("canonical_observations.csv"))
    seen = set()
    for f in candidates:
        if f in seen:
            continue
        seen.add(f)
        if f.exists() and f.stat().st_size > 0:
            return f
    return None

def norm_cols(df):
    m = {}
    for c in df.columns:
        k = str(c).strip().lower().replace(" ", "_").replace("-", "_").replace("%","pct")
        m[c] = k
    return df.rename(columns=m)

def find_col(df, names):
    cols = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None

def classify_clock(ts):
    t = ts.time()
    if t < time(9,30): return "BEFORE_09:30"
    if t < time(9,45): return "09:30-09:45"
    if t < time(10,0): return "09:45-10:00"
    if t < time(10,15): return "10:00-10:15"
    return "10:15+"

def safe_num(s):
    return pd.to_numeric(s, errors="coerce")

def main():
    a = parse_args()
    root = Path(a.root)
    out = root / CACHE_DIR_NAME / OUT_NAME
    out.mkdir(parents=True, exist_ok=True)
    cache_file = pick_cache(root)

    summary = {
        "status":"FAILED",
        "cache_only":True,
        "raw_source_scan":False,
        "output_dir":str(out),
        "timestamp_source":str(cache_file) if cache_file else None,
        "cutoffs":list(CUTOFFS),
        "hard_validation_gate":0.8,
    }

    if cache_file is None:
        summary["reason"]="No timestamped canonical cache found."
        (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2)); return 2

    # Chunked read keeps memory bounded.
    usecols = None
    chunks = []
    for ch in pd.read_csv(cache_file, low_memory=False, chunksize=200000):
        ch = norm_cols(ch)
        ts = find_col(ch, ["timestamp","observation_timestamp","event_timestamp","datetime","date_time"])
        sym = find_col(ch, ["symbol","ticker"])
        dt = find_col(ch, ["trade_date","date","trading_date"])
        if ts is None or sym is None:
            continue
        ch["_ts"] = pd.to_datetime(ch[ts], errors="coerce")
        if dt is not None:
            ch["_date"] = pd.to_datetime(ch[dt], errors="coerce").dt.date
        else:
            ch["_date"] = ch["_ts"].dt.date
        ch["_symbol"] = ch[sym].astype(str).str.strip()
        ch = ch[ch["_ts"].notna() & ch["_symbol"].ne("") & ch["_date"].notna()]
        if not ch.empty:
            chunks.append(ch)
    if not chunks:
        summary["reason"]="Canonical cache was found but no usable timestamp/symbol rows were recovered."
        (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2)); return 3

    df = pd.concat(chunks, ignore_index=True)
    df = df.sort_values(["_symbol","_date","_ts"])
    df = df.drop_duplicates(["_symbol","_date","_ts"], keep="first")

    # Restrict to regular-session observations. We retain all evidence up to each cutoff.
    df["_clock"] = df["_ts"].map(classify_clock)
    df = df[df["_ts"].dt.time >= time(9,15)]

    # Identify a usable price field for subsequent-path calculation.
    close = find_col(df, ["close","current_price","cmp","price"])
    if close is None:
        # Try normalized aliases.
        close = next((c for c in df.columns if str(c).lower() in {"close","current_price","cmp","price"}), None)
    if close is None:
        summary["reason"]="No usable close/current-price field in canonical cache."
        (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2)); return 4
    df["_px"] = safe_num(df[close])

    # Evidence columns: preserve only columns that can be interpreted without inventing fields.
    evidence_cols = []
    for c in ["price_direction","direction_agreement","core_evidence_count","magnitude_count",
              "strength_bucket","persistent","option_direction","fut_direction","price_chg_pct",
              "volume_pct","ce_num","pe_num","pec_num","ce_pct","pe_pct","pec_pct","fut_num","fut_pct","fut_state"]:
        if c in df.columns:
            evidence_cols.append(c)

    cohorts = []
    summaries = []
    for label, cutoff in CUTOFFS.items():
        # Latest observation available by cutoff per symbol/date.
        eligible = df[df["_ts"].dt.time <= cutoff]
        latest = eligible.groupby(["_symbol","_date"], as_index=False).tail(1).copy()
        latest["_maturity"] = label
        latest["_maturity_ts"] = latest["_ts"]

        # Subsequent price path for same symbol/date.
        rows = []
        for key, g in df.groupby(["_symbol","_date"], sort=False):
            if key not in set(map(tuple, latest[["_symbol","_date"]].itertuples(index=False, name=None))):
                continue
            arow = latest[(latest["_symbol"]==key[0]) & (latest["_date"]==key[1])]
            if arow.empty: continue
            anchor = arow.iloc[-1]
            after = g[g["_ts"] > anchor["_ts"]]
            after = after[after["_px"].notna()]
            p0 = anchor["_px"]
            if pd.isna(p0) or after.empty:
                favorable = adverse = final = None
            else:
                moves = (after["_px"] - p0) / p0 * 100.0
                # Direction inferred from anchor price_direction only; unknown stays unknown.
                d = str(anchor.get("price_direction","")).upper()
                sign = -1 if "DOWN" in d else (1 if "UP" in d else None)
                if sign is None:
                    favorable = float(moves.max()) if not moves.empty else None
                    adverse = float(moves.min()) if not moves.empty else None
                    final = float(moves.iloc[-1])
                else:
                    signed = moves * sign
                    favorable = float(signed.max())
                    adverse = float(signed.min())
                    final = float(signed.iloc[-1])
            hit = (favorable is not None and favorable >= 0.5)
            hold = (final is not None and final >= 0.5)
            rows.append({
                "symbol":key[0],"trade_date":str(key[1]),"maturity":label,
                "anchor_timestamp":str(anchor["_ts"]),
                "anchor_price":float(p0) if pd.notna(p0) else None,
                "favorable_pct":favorable,"adverse_pct":adverse,"final_pct":final,
                "reached_0_5x":hit,"held_0_5x":hold,
                "path_rows_after_anchor":int(len(after)),
                "price_direction":anchor.get("price_direction",""),
                "strength_bucket":anchor.get("strength_bucket",""),
                "core_evidence_count":anchor.get("core_evidence_count",""),
                "magnitude_count":anchor.get("magnitude_count",""),
            })
        r = pd.DataFrame(rows)
        cohorts.append(r)
        if r.empty:
            summaries.append({"maturity":label,"n":0})
        else:
            summaries.append({
                "maturity":label,"n":int(len(r)),
                "symbols":int(r.symbol.nunique()),
                "dates":int(r.trade_date.nunique()),
                "hit_rate":float(r.reached_0_5x.mean()),
                "holding_rate":float(r.held_0_5x.mean()),
                "mean_favorable_pct":float(pd.to_numeric(r.favorable_pct,errors="coerce").mean()),
                "mean_adverse_pct":float(pd.to_numeric(r.adverse_pct,errors="coerce").mean()),
                "mean_final_pct":float(pd.to_numeric(r.final_pct,errors="coerce").mean()),
            })

    allc = pd.concat(cohorts, ignore_index=True) if cohorts else pd.DataFrame()
    allc.to_csv(out/"maturity_anchor_outcomes.csv", index=False)
    pd.DataFrame(summaries).to_csv(out/"maturity_window_summary.csv", index=False)

    # Compare the same symbol/date across maturities where possible.
    if not allc.empty:
        pivot = allc.pivot_table(index=["symbol","trade_date"], columns="maturity",
                                 values=["reached_0_5x","held_0_5x","favorable_pct","final_pct"],
                                 aggfunc="last")
        pivot.reset_index().to_csv(out/"maturity_comparison_by_pair.csv", index=False)

    summary.update({
        "status":"READY",
        "canonical_rows":int(len(df)),
        "symbols":int(df["_symbol"].nunique()),
        "dates":int(df["_date"].nunique()),
        "timestamped_rows":int(df["_ts"].notna().sum()),
        "price_rows":int(df["_px"].notna().sum()),
        "maturity_results":summaries,
        "evidence_columns_present":evidence_cols,
        "note":"Timestamp-aware descriptive study. For each cutoff, only the latest observation available by that cutoff is used as the anchor; subsequent rows are used only for forward outcome measurement. No strategy is accepted or optimized; >=80% remains the hard validation gate."
    })
    (out/"time_maturity_summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
