"""
NTIS SDL V12.7 Historical Band Scanner
Research-only scanner. Does not modify the SDL production/dashboard.

Purpose
-------
Compare each current stock row against the historically validated V12.6
candidate population and report the historical holdout band represented by
the exact factor/state matches.

Historical bands
----------------
<65%
65-<70%
70-<72%
72%+

The scanner does NOT claim that the stock has that probability. The rate is
the historical holdout rate of the matched candidate(s).

Expected current-input CSV
---------------------------
One row per stock/maturity/ORB context with columns matching the V8 feature
names used by the candidate catalogue. V8 exact factors are:
orb_minutes, maturity, orb_dir, price_dir, fut_dir, option_dir, fut_state,
volume_state, ce_state, pe_state, pec_state, fut_oi_state, ce_pct_state,
pe_pct_state, pec_pct_state, fut_pct_state, price_state, orb_agree,
evidence_agreement, persistent, strength_bucket, core_count_band,
magnitude_count_band, orb_fut_agree, orb_price_agree.

Trajectory factors are also supported when present:
px_all_negative_pre_maturity, px_all_positive_pre_maturity,
px_negative_count_pre_maturity.

The script auto-discovers:
  .sector_intelligence/v12_6_exhaustive_research/chronological_validation_corrected.csv
or chronological_validation.csv

The current snapshot must be supplied explicitly:
  python .\v12_7_historical_band_scanner.py --input <current_snapshot.csv>

Output:
  .sector_intelligence/v12_7_historical_band_scanner/stock_band_scan.csv
  .sector_intelligence/v12_7_historical_band_scanner/v12_7_scanner_summary.json
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import pandas as pd

BASE = Path(__file__).resolve().parent
DEFAULT_OUT = BASE / ".sector_intelligence" / "v12_7_historical_band_scanner"

BANDS = [
    ("<65%", 0.0, 0.65, 0),
    ("65-<70%", 0.65, 0.70, 1),
    ("70-<72%", 0.70, 0.72, 2),
    ("72%+", 0.72, 1.01, 3),
]

V8_FACTOR_COLUMNS = [
    "orb_minutes", "maturity", "orb_dir", "price_dir", "fut_dir",
    "option_dir", "fut_state", "volume_state", "ce_state", "pe_state",
    "pec_state", "fut_oi_state", "ce_pct_state", "pe_pct_state",
    "pec_pct_state", "fut_pct_state", "price_state", "orb_agree",
    "evidence_agreement", "persistent", "strength_bucket",
    "core_count_band", "magnitude_count_band", "orb_fut_agree",
    "orb_price_agree",
]

TRAJ_FACTOR_COLUMNS = [
    "px_all_negative_pre_maturity",
    "px_all_positive_pre_maturity",
    "px_negative_count_pre_maturity",
]

def norm_value(v):
    if pd.isna(v):
        return None
    if isinstance(v, bool):
        return str(v).lower()
    s = str(v).strip()
    if s.lower() in {"nan", "none", ""}:
        return None
    return s

def parse_candidate(candidate_id):
    """Return [(factor, state), ...] from KIND|factor=value|..."""
    parts = str(candidate_id).split("|")
    pairs = []
    for token in parts[1:]:
        if "=" not in token:
            continue
        factor, value = token.split("=", 1)
        pairs.append((factor, value))
    return pairs

def band_for(rate):
    if rate is None or pd.isna(rate):
        return None, None
    r = float(rate)
    for label, lo, hi, rank in BANDS:
        if lo <= r < hi:
            return label, rank
    return None, None

def discover_validation(base):
    candidates = [
        base / ".sector_intelligence" / "v12_6_exhaustive_research" / "chronological_validation_corrected.csv",
        base / ".sector_intelligence" / "v12_6_exhaustive_research" / "chronological_validation.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    # Recursive fallback, but only under the research area.
    root = base / ".sector_intelligence"
    if root.exists():
        found = list(root.rglob("chronological_validation_corrected.csv"))
        if found:
            return found[0]
        found = list(root.rglob("chronological_validation.csv"))
        if found:
            return found[0]
    return None

def discover_input(base, explicit=None):
    """
    V12.7 deliberately requires an explicit current snapshot.

    Automatic discovery is disabled because research CSVs can have the same
    factor columns as a current intraday snapshot and would produce a
    technically valid but scientifically invalid scan.
    """
    if not explicit:
        raise ValueError(
            "V12.7 requires an explicit current intraday snapshot. "
            "Use --input <current_snapshot.csv>. Automatic CSV discovery is disabled."
        )

    p = Path(explicit)
    if not p.exists():
        raise FileNotFoundError(f"Current input CSV not found: {p}")

    forbidden_names = {
        "pattern_population.csv",
        "chronological_validation.csv",
        "chronological_validation_corrected.csv",
        "candidate_catalog.csv",
        "maturity_feature_matrix.csv",
        "phase3b_robust_population.csv",
        "phase3c_top50_robust_for_review.csv",
    }
    if p.name.lower() in {x.lower() for x in forbidden_names}:
        raise ValueError(
            f"Rejected input '{p.name}': this is a research/catalogue file, "
            "not a current intraday stock snapshot. Supply the actual current snapshot CSV."
        )

    return p

def prepare_validation(v):
    required = {"candidate_id", "holdout_rate", "holdout_n", "holdout_dates", "holdout_symbols"}
    missing = required - set(v.columns)
    if missing:
        raise ValueError(f"Validation file missing columns: {sorted(missing)}")

    v = v.copy()
    v["holdout_rate"] = pd.to_numeric(v["holdout_rate"], errors="coerce")
    v["holdout_n"] = pd.to_numeric(v["holdout_n"], errors="coerce")
    v["holdout_dates"] = pd.to_numeric(v["holdout_dates"], errors="coerce")
    v["holdout_symbols"] = pd.to_numeric(v["holdout_symbols"], errors="coerce")

    # Scanner catalogue: only robust holdout-supported candidates.
    v = v[
        v["holdout_rate"].notna()
        & (v["holdout_n"] >= 30)
        & (v["holdout_dates"] >= 3)
        & (v["holdout_symbols"] >= 10)
    ].copy()

    bands = v["holdout_rate"].map(band_for)
    v["historical_band"] = bands.map(lambda x: x[0])
    v["band_rank"] = bands.map(lambda x: x[1])
    v["pairs"] = v["candidate_id"].map(parse_candidate)
    return v

def row_matches(row, pairs):
    for factor, state in pairs:
        if factor not in row.index:
            return False
        rv = norm_value(row[factor])
        if rv is None:
            return False
        # Candidate values are stored as strings. Normalize booleans/numbers
        # without changing their semantic representation.
        if rv.lower() == str(state).strip().lower():
            continue
        try:
            if float(rv) == float(state):
                continue
        except Exception:
            pass
        return False
    return True

def scan_rows(current, validation):
    if "symbol" not in current.columns:
        raise ValueError("Current input must contain a 'symbol' column.")

    records = []
    for idx, row in current.iterrows():
        matches = []
        for _, cand in validation.iterrows():
            if row_matches(row, cand["pairs"]):
                matches.append(cand)

        if not matches:
            records.append({
                "input_row": idx,
                "symbol": row.get("symbol"),
                "trade_date": row.get("trade_date"),
                "orb_minutes": row.get("orb_minutes"),
                "maturity": row.get("maturity"),
                "historical_band": "NO_MATCH",
                "best_holdout_rate": None,
                "best_holdout_n": None,
                "best_holdout_dates": None,
                "best_holdout_symbols": None,
                "matched_candidates": 0,
                "matched_60_65": 0,
                "matched_65_70": 0,
                "matched_70_72": 0,
                "matched_72_plus": 0,
                "matched_candidate_ids": "",
            })
            continue

        m = pd.DataFrame(matches).sort_values(
            ["band_rank", "holdout_rate", "holdout_n"],
            ascending=[False, False, False]
        )
        best = m.iloc[0]
        records.append({
            "input_row": idx,
            "symbol": row.get("symbol"),
            "trade_date": row.get("trade_date"),
            "orb_minutes": row.get("orb_minutes"),
            "maturity": row.get("maturity"),
            "historical_band": best["historical_band"],
            "best_holdout_rate": float(best["holdout_rate"]),
            "best_holdout_n": int(best["holdout_n"]),
            "best_holdout_dates": int(best["holdout_dates"]),
            "best_holdout_symbols": int(best["holdout_symbols"]),
            "matched_candidates": int(len(m)),
            "matched_60_65": int((m["historical_band"] == "<65%").sum()),
            "matched_65_70": int((m["historical_band"] == "65-<70%").sum()),
            "matched_70_72": int((m["historical_band"] == "70-<72%").sum()),
            "matched_72_plus": int((m["historical_band"] == "72%+").sum()),
            "matched_candidate_ids": " || ".join(m["candidate_id"].astype(str).head(20)),
        })

    result = pd.DataFrame(records)
    # Ranking is intentionally non-weighted: historical band first, then
    # historical holdout rate and support. No invented confidence score.
    result["rank"] = 999999
    eligible = result["historical_band"] != "NO_MATCH"
    result.loc[eligible, "rank"] = (
        result.loc[eligible]
        .sort_values(
            ["best_holdout_rate", "best_holdout_n", "best_holdout_dates", "best_holdout_symbols"],
            ascending=[False, False, False, False]
        )
        .reset_index()
        .index + 1
    )
    return result.sort_values(["rank", "symbol"], na_position="last")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", default=None)
    ap.add_argument("--input", required=True, help="Explicit current intraday snapshot CSV")
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    validation_path = Path(args.validation) if args.validation else discover_validation(BASE)
    if validation_path is None:
        raise FileNotFoundError(
            "No V12.6 chronological validation file found. "
            "Expected chronological_validation_corrected.csv or chronological_validation.csv "
            "under .sector_intelligence\\v12_6_exhaustive_research."
        )

    input_path = discover_input(BASE, args.input)
    if input_path is None:
        raise FileNotFoundError(
            "No V8-compatible current stock CSV was auto-discovered. "
            "Run with --input <current_snapshot.csv>."
        )

    validation = prepare_validation(pd.read_csv(validation_path))
    current = pd.read_csv(input_path)

    # Scientific safety checks: this must look like a stock-level current
    # snapshot, not a historical outcome/research population.
    if "symbol" not in current.columns:
        raise ValueError("Current snapshot must contain a 'symbol' column.")
    if len(current) == 0:
        raise ValueError("Current snapshot is empty.")
    if "reached_0_5x" in current.columns:
        raise ValueError(
            "Rejected input: current scanner input must not contain the historical "
            "outcome column 'reached_0_5x'."
        )
    if "candidate_id" in current.columns:
        raise ValueError(
            "Rejected input: current scanner input must not contain 'candidate_id'. "
            "This appears to be a research catalogue/validation file."
        )

    # Keep only factor columns that actually exist in the current input.
    supported_factors = set(current.columns)
    validation = validation[
        validation["pairs"].map(lambda pairs: all(f in supported_factors for f, _ in pairs))
    ].copy()

    result = scan_rows(current, validation)
    result.to_csv(out / "stock_band_scan.csv", index=False)

    summary = {
        "status": "V12_7_HISTORICAL_BAND_SCANNER_COMPLETE",
        "production_modified": False,
        "validation_source": str(validation_path),
        "current_input": str(input_path),
        "current_input_mode": "explicit_only",
        "robust_historical_candidates_available": int(len(validation)),
        "current_rows_scanned": int(len(current)),
        "matched_rows": int((result["historical_band"] != "NO_MATCH").sum()),
        "no_match_rows": int((result["historical_band"] == "NO_MATCH").sum()),
        "band_counts": {
            b: int((result["historical_band"] == b).sum())
            for b, _, _, _ in BANDS
        },
        "interpretation": (
            "Historical holdout band of matched candidates; not an individual-stock "
            "probability or trading recommendation. No arbitrary weighted score is used."
        ),
        "frozen_gate": {
            "hit_rate": 0.80,
            "holdout_n": 30,
            "holdout_dates": 3,
            "holdout_symbols": 10,
        },
        "outputs": ["stock_band_scan.csv", "v12_7_scanner_summary.json"],
    }
    (out / "v12_7_scanner_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
