"""
NTIS SDL V12.6 — Exhaustive Research Miner
Research-only. Does not modify SDL production/dashboard code.

Purpose:
1. Consume the exact preserved V8 maturity_feature_matrix.csv.
2. Optionally enrich each symbol/date/maturity with point-in-time pre-maturity
   checkpoint features from canonical_strength_observations.csv.
3. Mine individual, 2-, 3-, and 4-factor exact-state combinations.
4. Mine sequential persistence combinations from checkpoint price/option/volume data.
5. Apply minimum support controls during discovery to prevent enormous sparse
   candidate populations.
6. Write a complete candidate catalog; outcome is measured, not used to invent
   feature definitions.

Important:
- Target is reached_0_5x exactly.
- 0.5x means 50% of opening straddle value; it is NOT a 0.5% price move.
- Missing is never converted to zero.
- No dashboard or production file is modified.
"""

from pathlib import Path
from itertools import combinations
import json
import math
import pandas as pd

BASE = Path(".")
V8 = BASE / ".sector_intelligence" / "maturity_conditional_pattern_discovery_v8" / "maturity_feature_matrix.csv"
CANON = BASE / ".sector_intelligence" / "data_strength_combination_study" / "canonical_strength_observations.csv"
OUT = BASE / ".sector_intelligence" / "v12_6_exhaustive_research"

MIN_N = 30
MIN_DATES = 3
MIN_SYMBOLS = 10
MAX_FACTORS = 4

# These are the effective V8 feature columns. We intentionally use the exact
# matrix rather than reconstructing their semantics.
V8_FEATURES = [
    "orb_agree","orb_price_agree","orb_fut_agree","price_dir","price_state",
    "option_dir","ce_state","pe_state","pec_state","ce_pct_state","pe_pct_state",
    "pec_pct_state","fut_dir","fut_state","fut_oi_state","fut_pct_state",
    "volume_state","evidence_agreement","persistent","strength_bucket",
    "core_count_band","magnitude_count_band"
]

def norm_date(s):
    return pd.to_datetime(s, errors="coerce").dt.date

def safe_token(v):
    if pd.isna(v):
        return "<MISSING>"
    return str(v)

def add_checkpoint_features(df, canon):
    """Add outcome-independent pre-maturity trajectory features."""
    if canon is None or canon.empty:
        return df

    c = canon.copy()
    c["timestamp"] = pd.to_datetime(c["timestamp"], errors="coerce")
    c["trade_date"] = norm_date(c["trade_date"])
    c = c.dropna(subset=["symbol","trade_date","timestamp"])
    c = c.sort_values(["symbol","trade_date","timestamp"])

    # Checkpoints are deliberately before each maturity.
    maturity_minutes = {"09:30": 570, "09:45": 585, "10:00": 600, "10:15": 615}
    rows = []
    for (sym, day), g in c.groupby(["symbol","trade_date"], sort=False):
        g = g.sort_values("timestamp")
        for mat, mat_min in maturity_minutes.items():
            available = g[g["timestamp"].dt.hour * 60 + g["timestamp"].dt.minute < mat_min]
            cps = [570-5,570,575,580,585,590,595,600,605,610]
            # Keep only checkpoints strictly before maturity.
            cps = [x for x in cps if x < mat_min]
            rec = {"symbol": sym, "trade_date": day, "maturity": mat}
            vals = {}
            for cm in cps:
                z = available[(available["timestamp"].dt.hour*60 + available["timestamp"].dt.minute) <= cm]
                if z.empty:
                    continue
                r = z.iloc[-1]
                tag = f"{cm//60:02d}{cm%60:02d}"
                vals[tag] = r
                if "price_chg_pct" in r:
                    rec[f"px_{tag}"] = r["price_chg_pct"]
                if "ce_pct" in r:
                    rec[f"ce_{tag}"] = r["ce_pct"]
                if "pe_pct" in r:
                    rec[f"pe_{tag}"] = r["pe_pct"]
                if "pec_pct" in r:
                    rec[f"pec_{tag}"] = r["pec_pct"]
                if "volume_pct" in r:
                    rec[f"vol_{tag}"] = r["volume_pct"]
            # Outcome-independent persistence states.
            pxcols = [k for k in rec if k.startswith("px_")]
            if pxcols:
                ordered = sorted(pxcols)
                rec["px_all_negative_pre_maturity"] = bool(pd.Series([rec[k] for k in ordered]).notna().all() and pd.Series([rec[k] for k in ordered]).lt(0).all())
                rec["px_all_positive_pre_maturity"] = bool(pd.Series([rec[k] for k in ordered]).notna().all() and pd.Series([rec[k] for k in ordered]).gt(0).all())
                rec["px_negative_count_pre_maturity"] = int(pd.Series([rec[k] for k in ordered]).lt(0).sum())
                rec["px_checkpoint_count"] = len(ordered)
            rows.append(rec)
    if not rows:
        return df
    traj = pd.DataFrame(rows)
    return df.merge(traj, on=["symbol","trade_date","maturity"], how="left")

def group_result(g, factor_names, values, kind):
    y = g["reached_0_5x"].astype(bool)
    return {
        "candidate_id": f"{kind}|" + "|".join(f"{f}={v}" for f,v in zip(factor_names,values)),
        "kind": kind,
        "factor_count": len(factor_names),
        "factors": "|".join(factor_names),
        "states": "|".join(map(str,values)),
        "n": int(len(g)),
        "good_n": int(y.sum()),
        "bad_n": int((~y).sum()),
        "rate": float(y.mean()),
        "dates": int(g["trade_date"].nunique()),
        "symbols": int(g["symbol"].nunique()),
        "maturity_count": int(g["maturity"].nunique()),
        "orb_minutes_count": int(g["orb_minutes"].nunique()),
    }

def mine_exact(df, features):
    results = []
    for k in range(1, MAX_FACTORS+1):
        for cols in combinations(features, k):
            # Cross-family combinations are preferred. Single-family combinations
            # are still retained for completeness.
            grp = df.groupby(list(cols), dropna=False, observed=True)
            for vals, g in grp:
                if not isinstance(vals, tuple):
                    vals = (vals,)
                if len(g) < MIN_N:
                    continue
                if g["trade_date"].nunique() < MIN_DATES or g["symbol"].nunique() < MIN_SYMBOLS:
                    continue
                results.append(group_result(g, cols, vals, "V8_EXACT"))
    return pd.DataFrame(results)

def mine_trajectory(df):
    results = []
    traj_cols = [
        "px_all_negative_pre_maturity","px_all_positive_pre_maturity",
        "px_negative_count_pre_maturity"
    ]
    available = [c for c in traj_cols if c in df.columns]
    # Do not enumerate arbitrary numeric counts with V8 features here.
    for c in available:
        g0 = df[df[c].notna()].copy()
        if g0.empty:
            continue
        for value, g in g0.groupby(c, dropna=False):
            if len(g) >= MIN_N and g.trade_date.nunique() >= MIN_DATES and g.symbol.nunique() >= MIN_SYMBOLS:
                results.append(group_result(g, [c], [value], "TRAJECTORY"))
    # Combine trajectory states with each V8 feature and with pairs of V8 features.
    for k in (1,2):
        for vcols in combinations(V8_FEATURES, k):
            cols = tuple(vcols) + ("px_all_negative_pre_maturity",)
            if cols[-1] not in df.columns:
                continue
            for vals, g in df.groupby(list(cols), dropna=False, observed=True):
                if not isinstance(vals, tuple):
                    vals = (vals,)
                if len(g) < MIN_N or g.trade_date.nunique() < MIN_DATES or g.symbol.nunique() < MIN_SYMBOLS:
                    continue
                results.append(group_result(g, cols, vals, "V8_PLUS_TRAJECTORY"))
    return pd.DataFrame(results)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not V8.exists():
        raise FileNotFoundError(f"Exact V8 matrix not found: {V8}")
    df = pd.read_csv(V8)
    df["trade_date"] = norm_date(df["trade_date"])
    df["reached_0_5x"] = df["reached_0_5x"].astype(bool)

    canon = None
    if CANON.exists():
        canon = pd.read_csv(CANON)
        df = add_checkpoint_features(df, canon)

    exact = mine_exact(df, V8_FEATURES)
    traj = mine_trajectory(df)
    allc = pd.concat([exact, traj], ignore_index=True) if not exact.empty or not traj.empty else pd.DataFrame()
    if not allc.empty:
        allc = allc.drop_duplicates("candidate_id")
        allc["passes_support"] = (
            (allc["n"] >= MIN_N) &
            (allc["dates"] >= MIN_DATES) &
            (allc["symbols"] >= MIN_SYMBOLS)
        )
        allc = allc.sort_values(["rate","n"], ascending=[False,False])
    allc.to_csv(OUT / "candidate_catalog.csv", index=False)

    summary = {
        "status": "V12_6_EXHAUSTIVE_MINING_COMPLETE",
        "production_modified": False,
        "exact_v8_matrix": str(V8),
        "canonical_available": bool(CANON.exists()),
        "target": "reached_0_5x",
        "target_semantics": "50% of opening straddle value",
        "min_n": MIN_N,
        "min_dates": MIN_DATES,
        "min_symbols": MIN_SYMBOLS,
        "max_factors": MAX_FACTORS,
        "candidate_count": int(len(allc)),
        "v8_exact_candidate_count": int(len(exact)),
        "trajectory_candidate_count": int(len(traj)),
        "note": "Candidate discovery is outcome-measured, not outcome-defined. Holdout validation is performed by the second script."
    }
    (OUT / "v12_6_mining_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
