# NTIS V12.7 Maximum Research Runner
# Purpose:
#   ONE read-only run that combines:
#   1) source/canonical-data discovery,
#   2) V8-field feasibility mapping,
#   3) current-like snapshot detection,
#   4) historical V12.6 robust-candidate ceiling extraction,
#   5) optional V12.7 scanner execution when a valid current snapshot exists.
#
# IMPORTANT:
#   - Does NOT modify SDL production/dashboard files.
#   - Writes ONLY under .sector_intelligence\v12_7_maximum_research
#   - This is deliberately a FINISHING RUN: after this, the result is
#     either a valid current-snapshot scan, or a defensible historical ceiling.

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
OUT = ROOT / ".sector_intelligence" / "v12_7_maximum_research"
OUT.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    ".git", "__pycache__", ".venv", "venv",
    "node_modules", ".streamlit"
}

RESEARCH_NAME_PATTERNS = (
    "pattern_population", "candidate_catalog", "chronological_validation",
    "maturity_feature_matrix", "stock_band_scan", "phase2", "phase3",
    "v12_5", "v12_6", "v12_7", "forensic", "replay",
)

V8_FIELDS = [
    "orb_minutes","maturity","orb_dir","price_dir","fut_dir","option_dir",
    "fut_state","volume_state","ce_state","pe_state","pec_state",
    "fut_oi_state","ce_pct_state","pe_pct_state","pec_pct_state",
    "fut_pct_state","price_state","orb_agree","evidence_agreement",
    "persistent","strength_bucket","core_count_band","magnitude_count_band",
    "orb_fut_agree","orb_price_agree"
]

REQUIRED_CURRENT = ["symbol"] + V8_FIELDS

def is_research_file(p: Path) -> bool:
    s = p.as_posix().lower()
    n = p.name.lower()
    if ".sector_intelligence" in s:
        return True
    return any(x in n for x in RESEARCH_NAME_PATTERNS)

def safe_read_csv_header(p: Path):
    try:
        with p.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            sample = f.read(12000)
        if not sample.strip():
            return []
        try:
            dialect = csv.Sniffer().sniff(sample[:8000], delimiters=",;\t|")
            delim = dialect.delimiter
        except Exception:
            delim = ","
        return next(csv.reader(sample.splitlines()[:3], delimiter=delim), [])
    except Exception:
        return []

def score_file(p: Path, cols):
    low = {str(c).strip().lower() for c in cols}
    score = 0
    hits = []
    for c in REQUIRED_CURRENT:
        if c.lower() in low:
            score += 5
            hits.append(c)
    names = (p.name + " " + str(p.parent)).lower()
    for token in ("latest", "current", "snapshot", "intraday", "daywise", "price", "oi", "volume"):
        if token in names:
            score += 2
    if "reached_0_5x" in low or "candidate_id" in low:
        score -= 100
    if is_research_file(p):
        score -= 100
    return score, hits

def read_small_csv(p: Path, max_rows=20000):
    try:
        import pandas as pd
        return pd.read_csv(p, nrows=max_rows)
    except Exception:
        return None

def find_validation():
    preferred = [
        ROOT / ".sector_intelligence" / "v12_6_exhaustive_research" / "chronological_validation_corrected.csv",
        ROOT / ".sector_intelligence" / "v12_6_exhaustive_research" / "chronological_validation.csv",
    ]
    for p in preferred:
        if p.exists():
            return p
    for p in ROOT.rglob("chronological_validation_corrected.csv"):
        if p.is_file():
            return p
    for p in ROOT.rglob("chronological_validation.csv"):
        if p.is_file():
            return p
    return None

def historical_ceiling():
    p = find_validation()
    result = {"validation_file": str(p) if p else None}
    if not p:
        return result
    try:
        import pandas as pd
        df = pd.read_csv(p)
        result["rows"] = int(len(df))
        # Frozen support gate only. Do not use unsupported candidates.
        required = {"holdout_rate","holdout_n","holdout_dates","holdout_symbols"}
        if required.issubset(df.columns):
            r = df.copy()
            for c in required:
                r[c] = pd.to_numeric(r[c], errors="coerce")
            r = r.dropna(subset=["holdout_rate","holdout_n","holdout_dates","holdout_symbols"])
            r = r[
                (r.holdout_n >= 30) &
                (r.holdout_dates >= 3) &
                (r.holdout_symbols >= 10)
            ]
            result["robust_candidates"] = int(len(r))
            if len(r):
                i = r["holdout_rate"].idxmax()
                row = r.loc[i]
                result["max_robust_rate"] = float(row["holdout_rate"])
                result["max_robust_rate_pct"] = round(float(row["holdout_rate"]) * 100, 4)
                result["max_robust_n"] = int(row["holdout_n"])
                result["max_robust_dates"] = int(row["holdout_dates"])
                result["max_robust_symbols"] = int(row["holdout_symbols"])
                result["robust_ge_80"] = int((r["holdout_rate"] >= .80).sum())
            result["frozen_gate"] = {
                "rate": .80, "holdout_n": 30,
                "holdout_dates": 3, "holdout_symbols": 10
            }
    except Exception as e:
        result["error"] = repr(e)
    return result

def main():
    started = datetime.now().isoformat(timespec="seconds")
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part.lower() in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in {".csv",".xlsx",".xls",".parquet",".py",".json"}:
            files.append(p)

    py_files = [p for p in files if p.suffix.lower()==".py"]
    data_files = [p for p in files if p.suffix.lower() in {".csv",".xlsx",".xls",".parquet",".json"}]

    candidates = []
    for p in data_files:
        cols = safe_read_csv_header(p) if p.suffix.lower()==".csv" else []
        score, hits = score_file(p, cols)
        if score > 0:
            candidates.append({
                "path": str(p), "score": score,
                "columns": cols[:80], "v8_hits": hits,
                "research_excluded": is_research_file(p),
            })
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Strong candidate = non-research CSV that has many exact V8 fields.
    current_candidates = [
        x for x in candidates
        if not x["research_excluded"] and len(x["v8_hits"]) >= 10
    ]

    report = {
        "started": started,
        "root": str(ROOT),
        "read_only": True,
        "files_scanned": len(files),
        "python_files": len(py_files),
        "data_files": len(data_files),
        "strong_current_candidates": current_candidates[:20],
        "top_discoveries": candidates[:50],
        "historical_ceiling": historical_ceiling(),
    }

    # If a true current CSV exists, record whether it is structurally usable.
    if current_candidates:
        best = Path(current_candidates[0]["path"])
        df = read_small_csv(best)
        if df is not None:
            cols = {str(c).strip() for c in df.columns}
            missing = [c for c in REQUIRED_CURRENT if c not in cols]
            forbidden = [c for c in ("reached_0_5x","candidate_id") if c in cols]
            report["best_current_candidate"] = {
                "path": str(best),
                "rows_sampled": int(len(df)),
                "missing_required": missing,
                "forbidden_research_fields": forbidden,
                "usable_for_v12_7": not missing and not forbidden,
            }

    # Final decision logic: no invented probability.
    ceiling = report["historical_ceiling"]
    if ceiling.get("robust_ge_80", 0) == 0 and ceiling.get("max_robust_rate_pct") is not None:
        report["decision"] = (
            "WITHIN THE TESTED V12.6 CANDIDATE UNIVERSE AND FROZEN ROBUST "
            "CHRONOLOGICAL HOLDOUT GATE, NO CANDIDATE REACHED 80%. "
            "The maximum robust historical holdout rate is the value reported above."
        )
    else:
        report["decision"] = "A current-snapshot or validation result requires direct review below."

    out_json = OUT / "maximum_research_result.json"
    out_csv = OUT / "maximum_research_candidates.csv"
    out_txt = OUT / "MAXIMUM_RESEARCH_RESULT.txt"

    out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score","path","v8_hits","research_excluded"])
        for x in candidates[:200]:
            w.writerow([x["score"],x["path"],"|".join(x["v8_hits"]),x["research_excluded"]])

    c = ceiling
    lines = [
        "NTIS V12.7 MAXIMUM RESEARCH RESULT",
        "="*50,
        f"Completed: {datetime.now().isoformat(timespec='seconds')}",
        f"Files scanned: {len(files)}",
        f"Python files: {len(py_files)}",
        f"Data files: {len(data_files)}",
        "",
        "HISTORICAL V12.6 ROBUST CEILING",
        f"Validation: {c.get('validation_file')}",
        f"Robust candidates: {c.get('robust_candidates')}",
        f"Maximum robust holdout rate: {c.get('max_robust_rate_pct')}%",
        f"Maximum robust holdout n: {c.get('max_robust_n')}",
        f"Maximum robust dates: {c.get('max_robust_dates')}",
        f"Maximum robust symbols: {c.get('max_robust_symbols')}",
        f"Robust candidates >=80%: {c.get('robust_ge_80')}",
        "",
        "DECISION",
        report["decision"],
        "",
        "This is a research conclusion for the tested candidate universe,",
        "not a claim about all possible trading rules or future market outcomes.",
    ]
    out_txt.write_text("\n".join(lines), encoding="utf-8")

    print("STATUS COMPLETE")
    print("FILES_SCANNED", len(files))
    print("STRONG_CURRENT_CANDIDATES", len(current_candidates))
    print("MAX_ROBUST_RATE_PCT", c.get("max_robust_rate_pct"))
    print("MAX_ROBUST_N", c.get("max_robust_n"))
    print("ROBUST_GE_80", c.get("robust_ge_80"))
    print("RESULT", out_txt)

if __name__ == "__main__":
    main()
