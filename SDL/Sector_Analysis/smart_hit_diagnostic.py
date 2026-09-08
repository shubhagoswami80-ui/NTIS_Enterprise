"""
NTIS SDL Smart Hit Diagnostic V1
Cache-first analysis of the latest Smart Replay & Hit Discovery results.

Purpose:
- Do NOT rescan XLSX files.
- Inspect existing result CSVs and/or canonical cache.
- Produce a compact diagnostic of where the current 5M/10M/15M discovery
  performed best and how outcomes split between excursion/holding/retrace.
- Preserve 67% as an interesting research threshold and 80% as the hard gate.
"""

from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

DEFAULT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
RESULT_HINTS = [
    ".sector_intelligence/smart_replay_strategy_study",
    ".sector_intelligence/data_strength_combination_study",
]

def find_csvs(root: Path):
    found = []
    for rel in RESULT_HINTS:
        p = root / rel
        if p.exists():
            found.extend(p.rglob("*.csv"))
    # Also inspect the intelligence root, but only CSVs; no XLSX traversal.
    ir = root / ".sector_intelligence"
    if ir.exists():
        found.extend(ir.glob("*.csv"))
        found.extend(ir.rglob("*pattern*.csv"))
        found.extend(ir.rglob("*outcome*.csv"))
        found.extend(ir.rglob("*result*.csv"))
    return sorted(set(found))

def pick_columns(df):
    low = {str(c).lower().strip(): c for c in df.columns}
    def get(*names):
        for n in names:
            if n in low: return low[n]
        return None
    return {
        "rate": get("hit_rate","success_rate","favorable_rate","win_rate"),
        "valid": get("valid_outcomes","n","sample","count","outcomes"),
        "window": get("orb_window","window","orb_minutes"),
        "pattern": get("pattern","pattern_name","features","rule"),
        "outcome": get("outcome","path_class","path_outcome"),
        "status": get("status","result"),
        "dates": get("dates","distinct_dates","date_count"),
        "symbols": get("symbols","distinct_symbols","symbol_count"),
    }

def summarize_file(p):
    try:
        df = pd.read_csv(p, low_memory=False)
    except Exception:
        return None
    if df.empty:
        return None
    cols = pick_columns(df)
    rate = cols["rate"]
    if rate is not None:
        s = pd.to_numeric(df[rate], errors="coerce")
        if s.notna().any():
            out = df.loc[s.notna()].copy()
            out["_rate"] = s[s.notna()].astype(float).values
            return p, out, cols
    return p, df, cols

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.root)
    outdir = Path(a.out) if a.out else root / ".sector_intelligence" / "smart_hit_diagnostic"
    outdir.mkdir(parents=True, exist_ok=True)

    files = find_csvs(root)
    summaries = []
    for p in files:
        r = summarize_file(p)
        if r: summaries.append(r)

    rows = []
    for p, df, c in summaries:
        if "_rate" in df:
            for _, row in df.iterrows():
                rows.append({
                    "source_file": str(p),
                    "orb_window": row.get(c["window"], "") if c["window"] else "",
                    "pattern": row.get(c["pattern"], "") if c["pattern"] else "",
                    "rate": row["_rate"],
                    "valid_outcomes": row.get(c["valid"], "") if c["valid"] else "",
                    "dates": row.get(c["dates"], "") if c["dates"] else "",
                    "symbols": row.get(c["symbols"], "") if c["symbols"] else "",
                    "outcome": row.get(c["outcome"], "") if c["outcome"] else "",
                })

    result = {
        "csv_files_seen": len(files),
        "rate_rows_found": len(rows),
        "status": "NO_RATE_RESULT_FILES_FOUND" if not rows else "DIAGNOSTIC_READY",
    }

    if rows:
        tab = pd.DataFrame(rows)
        tab = tab.sort_values(["rate"], ascending=False)
        tab.to_csv(outdir / "top_hit_candidates.csv", index=False)

        def numeric(col):
            return pd.to_numeric(tab[col], errors="coerce") if col in tab else pd.Series(dtype=float)

        rates = numeric("rate")
        result.update({
            "max_rate": float(rates.max()),
            "count_ge_67": int((rates >= .67).sum()),
            "count_ge_80": int((rates >= .80).sum()),
            "count_60_67": int(((rates >= .60) & (rates < .67)).sum()),
        })

        win = tab["orb_window"].astype(str).str.extract(r"(\d+)")[0]
        tab["_window_num"] = pd.to_numeric(win, errors="coerce")
        wm = []
        for w, g in tab.dropna(subset=["_window_num"]).groupby("_window_num"):
            rr = numeric_from = pd.to_numeric(g["rate"], errors="coerce").dropna()
            wm.append({"orb_window_min": int(w), "patterns": len(g),
                       "max_rate": float(rr.max()) if len(rr) else None,
                       "median_rate": float(rr.median()) if len(rr) else None,
                       "ge_67": int((rr >= .67).sum())})
        pd.DataFrame(wm).sort_values("orb_window_min").to_csv(outdir / "orb_window_summary.csv", index=False)

    (outdir / "diagnostic_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("SMART_HIT_DIAGNOSTIC:", json.dumps(result, default=str))
    if rows:
        print("TOP_RESULTS:", str((outdir / "top_hit_candidates.csv")))
        print("WINDOW_RESULTS:", str((outdir / "orb_window_summary.csv")))
    else:
        print("NEXT_REQUIRED: run Smart V4.1 with result-output enabled; no XLSX rescan requested.")

if __name__ == "__main__":
    main()
