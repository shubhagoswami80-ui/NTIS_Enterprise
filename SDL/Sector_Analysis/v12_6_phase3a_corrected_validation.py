"""
NTIS SDL V12.6 Phase 3A — Corrected Chronological Validation + Forensics
Research-only. Does not modify SDL production/dashboard files.

Purpose:
1. Re-validate the V12.6 candidate catalog without the trajectory-validation defect
   in the original validator.
2. Audit reached_0_5x dtype/values before calculating rates.
3. Reconstruct the same outcome-independent pre-maturity trajectory features used
   by the miner from canonical_strength_observations.csv.
4. Validate V8_EXACT, TRAJECTORY, and V8_PLUS_TRAJECTORY candidates correctly.
5. Produce candidate-population forensics without cherry-picking.

Frozen design:
- Train: 2026-08-14 through 2026-08-28
- Holdout: 2026-08-31 through 2026-09-04
- Gate: >=80% hit rate, >=30 holdout outcomes, >=3 holdout dates, >=10 holdout symbols
"""

from pathlib import Path
from itertools import combinations
import json
import pandas as pd
import numpy as np

BASE = Path(".")
V8 = BASE / ".sector_intelligence" / "maturity_conditional_pattern_discovery_v8" / "maturity_feature_matrix.csv"
CANON = BASE / ".sector_intelligence" / "data_strength_combination_study" / "canonical_strength_observations.csv"
OUT = BASE / ".sector_intelligence" / "v12_6_exhaustive_research"

TRAIN_START = pd.Timestamp("2026-08-14").date()
TRAIN_END = pd.Timestamp("2026-08-28").date()
HOLD_START = pd.Timestamp("2026-08-31").date()
HOLD_END = pd.Timestamp("2026-09-04").date()

GATE_RATE = 0.80
GATE_N = 30
GATE_DATES = 3
GATE_SYMBOLS = 10

V8_FEATURES = [
    "orb_agree","orb_price_agree","orb_fut_agree","price_dir","price_state",
    "option_dir","ce_state","pe_state","pec_state","ce_pct_state","pe_pct_state",
    "pec_pct_state","fut_dir","fut_state","fut_oi_state","fut_pct_state",
    "volume_state","evidence_agreement","persistent","strength_bucket",
    "core_count_band","magnitude_count_band"
]

def norm_date(s):
    return pd.to_datetime(s, errors="coerce").dt.date

def parse_bool_series(s, name):
    raw = s.copy()
    if pd.api.types.is_bool_dtype(raw):
        return raw.astype(bool), {"dtype": str(s.dtype), "invalid_values": [], "mapping": "native_bool"}
    z = raw.astype(str).str.strip().str.lower()
    mapping = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False}
    invalid = sorted(set(z.dropna()) - set(mapping))
    if invalid:
        raise ValueError(f"{name} contains unsupported boolean values: {invalid[:20]}")
    return z.map(mapping).astype(bool), {"dtype": str(s.dtype), "invalid_values": invalid, "mapping": mapping}

def add_checkpoint_features(df, canon):
    c = canon.copy()
    c["timestamp"] = pd.to_datetime(c["timestamp"], errors="coerce")
    c["trade_date"] = norm_date(c["trade_date"])
    c = c.dropna(subset=["symbol","trade_date","timestamp"])
    c = c.sort_values(["symbol","trade_date","timestamp"])

    maturity_minutes = {"09:30": 570, "09:45": 585, "10:00": 600, "10:15": 615}
    rows = []
    for (sym, day), g in c.groupby(["symbol","trade_date"], sort=False):
        g = g.sort_values("timestamp")
        for mat, mat_min in maturity_minutes.items():
            available = g[g["timestamp"].dt.hour * 60 + g["timestamp"].dt.minute < mat_min]
            cps = [565,570,575,580,585,590,595,600,605,610]
            cps = [x for x in cps if x < mat_min]
            rec = {"symbol": sym, "trade_date": day, "maturity": mat}
            for cm in cps:
                z = available[(available["timestamp"].dt.hour*60 + available["timestamp"].dt.minute) <= cm]
                if z.empty:
                    continue
                r = z.iloc[-1]
                tag = f"{cm//60:02d}{cm%60:02d}"
                for src, dst in [
                    ("price_chg_pct", f"px_{tag}"),
                    ("ce_pct", f"ce_{tag}"),
                    ("pe_pct", f"pe_{tag}"),
                    ("pec_pct", f"pec_{tag}"),
                    ("volume_pct", f"vol_{tag}"),
                ]:
                    if src in r.index:
                        rec[dst] = r[src]
            pxcols = sorted([k for k in rec if k.startswith("px_")])
            if pxcols:
                vals = pd.to_numeric(pd.Series([rec[k] for k in pxcols]), errors="coerce")
                rec["px_all_negative_pre_maturity"] = bool(vals.notna().all() and vals.lt(0).all())
                rec["px_all_positive_pre_maturity"] = bool(vals.notna().all() and vals.gt(0).all())
                rec["px_negative_count_pre_maturity"] = int(vals.lt(0).sum())
                rec["px_checkpoint_count"] = int(vals.notna().sum())
            rows.append(rec)
    traj = pd.DataFrame(rows)
    return df.merge(traj, on=["symbol","trade_date","maturity"], how="left")

def parse_candidate(cid):
    parts = str(cid).split("|")
    kind = parts[0]
    pairs = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            pairs[k] = v
    return kind, pairs

def apply_candidate(df, pairs):
    mask = pd.Series(True, index=df.index)
    for col, val in pairs.items():
        if col not in df.columns:
            return df.iloc[0:0]
        if val == "<MISSING>":
            mask &= df[col].isna()
        else:
            # Match exactly as the miner's candidate tokens were serialized.
            mask &= df[col].astype(str).eq(val)
    return df[mask]

def stats(g):
    if g.empty:
        return {"n":0,"good_n":0,"bad_n":0,"rate":None,"dates":0,"symbols":0}
    y = g["reached_0_5x"]
    return {
        "n": int(len(g)),
        "good_n": int(y.sum()),
        "bad_n": int((~y).sum()),
        "rate": float(y.mean()),
        "dates": int(g["trade_date"].nunique()),
        "symbols": int(g["symbol"].nunique()),
    }

def validate_candidates(df, cat):
    rows = []
    for _, c in cat.iterrows():
        cid = c["candidate_id"]
        kind, pairs = parse_candidate(cid)
        g = apply_candidate(df, pairs)
        all_s = stats(g)
        train = g[(g.trade_date >= TRAIN_START) & (g.trade_date <= TRAIN_END)]
        hold = g[(g.trade_date >= HOLD_START) & (g.trade_date <= HOLD_END)]
        tr_s, ho_s = stats(train), stats(hold)
        final_pass = (
            ho_s["n"] >= GATE_N and ho_s["rate"] is not None and ho_s["rate"] >= GATE_RATE
            and ho_s["dates"] >= GATE_DATES and ho_s["symbols"] >= GATE_SYMBOLS
        )
        rows.append({
            "candidate_id": cid,
            "kind": kind,
            "factor_count": c.get("factor_count", None),
            "factors": c.get("factors", ""),
            "states": c.get("states", ""),
            "all_n": all_s["n"], "all_good_n": all_s["good_n"], "all_bad_n": all_s["bad_n"],
            "all_rate": all_s["rate"], "all_dates": all_s["dates"], "all_symbols": all_s["symbols"],
            "train_n": tr_s["n"], "train_good_n": tr_s["good_n"], "train_bad_n": tr_s["bad_n"],
            "train_rate": tr_s["rate"], "train_dates": tr_s["dates"], "train_symbols": tr_s["symbols"],
            "holdout_n": ho_s["n"], "holdout_good_n": ho_s["good_n"], "holdout_bad_n": ho_s["bad_n"],
            "holdout_rate": ho_s["rate"], "holdout_dates": ho_s["dates"], "holdout_symbols": ho_s["symbols"],
            "top_holdout_date_share": float(hold.trade_date.value_counts(normalize=True).iloc[0]) if not hold.empty else None,
            "top_holdout_symbol_share": float(hold.symbol.value_counts(normalize=True).iloc[0]) if not hold.empty else None,
            "frozen_final_gate_pass": bool(final_pass),
            "status": "FINAL_VALIDATION_CANDIDATE" if final_pass else ("HOLDOUT_RESEARCH" if ho_s["n"] > 0 else "NO_HOLDOUT_SUPPORT"),
        })
    return pd.DataFrame(rows)

def make_forensics(r):
    out = {}
    out["support_gate_counts"] = pd.DataFrame({
        "criterion": ["holdout_n>=30","holdout_dates>=3","holdout_symbols>=10","all_three"],
        "candidate_count": [
            int((r.holdout_n >= 30).sum()),
            int((r.holdout_dates >= 3).sum()),
            int((r.holdout_symbols >= 10).sum()),
            int(((r.holdout_n >= 30)&(r.holdout_dates >= 3)&(r.holdout_symbols >= 10)).sum()),
        ]
    })

    bins = [-np.inf, .50, .60, .65, .70, .75, .80, np.inf]
    labels = ["<50%","50-<60%","60-<65%","65-<70%","70-<75%","75-<80%",">=80%"]
    rb = r[r.holdout_rate.notna()].copy()
    rb["holdout_rate_bin"] = pd.cut(rb["holdout_rate"], bins=bins, labels=labels, right=False)
    out["holdout_rate_distribution"] = rb.groupby("holdout_rate_bin", observed=False).size().rename("candidate_count").reset_index()

    out["factor_count_analysis"] = (
        r.groupby(["kind","factor_count"], dropna=False)
         .agg(candidate_count=("candidate_id","size"),
              max_holdout_rate=("holdout_rate","max"),
              median_holdout_rate=("holdout_rate","median"),
              n_ge_30=("holdout_n", lambda s: int((s>=30).sum())),
              n_ge_3_dates=("holdout_dates", lambda s: int((s>=3).sum())),
              n_ge_10_symbols=("holdout_symbols", lambda s: int((s>=10).sum())))
         .reset_index()
    )

    # Family frequency among candidates with meaningful holdout support and the
    # highest 200 holdout rates; descriptive only.
    top = r[(r.holdout_n >= GATE_N) & r.holdout_dates.ge(GATE_DATES) & r.holdout_symbols.ge(GATE_SYMBOLS)].copy()
    top = top.sort_values(["holdout_rate","holdout_n"], ascending=[False,False]).head(200)
    fam_rows = []
    for _, row in top.iterrows():
        for f in str(row["factors"]).split("|"):
            if f:
                fam_rows.append({"factor":f, "candidate_id":row["candidate_id"], "holdout_rate":row["holdout_rate"]})
    out["factor_frequency_analysis"] = (
        pd.DataFrame(fam_rows).groupby("factor").agg(candidate_count=("candidate_id","nunique"),
            mean_holdout_rate=("holdout_rate","mean")).reset_index().sort_values("candidate_count",ascending=False)
        if fam_rows else pd.DataFrame(columns=["factor","candidate_count","mean_holdout_rate"])
    )

    # Concentration of the best supported candidates.
    out["robust_candidate_shortlist"] = top.copy()

    # Candidate-family comparison.
    out["candidate_family_forensics"] = (
        r.groupby("kind").agg(candidate_count=("candidate_id","size"),
            holdout_supported=("holdout_n",lambda s:int((s>0).sum())),
            n_ge_30=("holdout_n",lambda s:int((s>=30).sum())),
            n_ge_3_dates=("holdout_dates",lambda s:int((s>=3).sum())),
            n_ge_10_symbols=("holdout_symbols",lambda s:int((s>=10).sum())),
            max_holdout_rate=("holdout_rate","max"),
            median_holdout_rate=("holdout_rate","median")).reset_index()
    )
    return out

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Locate the candidate catalogue produced by V12.6 Phase 1.
    # The original script had an undefined CAT variable; this version discovers
    # the catalogue by schema so the exact filename is not assumed.
    candidate_files = []
    search_roots = [OUT, BASE / ".sector_intelligence"]
    for root in search_roots:
        if root.exists():
            for f in root.rglob("*.csv"):
                if f.name == "chronological_validation.csv" or f.name == "chronological_validation_corrected.csv":
                    continue
                try:
                    cols = pd.read_csv(f, nrows=0).columns.tolist()
                except Exception:
                    continue
                if "candidate_id" in cols:
                    candidate_files.append(f)
    # Prefer the exhaustive-research directory and the largest catalogue.
    candidate_files = sorted(set(candidate_files), key=lambda x: (x.parent != OUT, -x.stat().st_size))
    if not V8.exists() or not candidate_files:
        raise FileNotFoundError(f"Required files missing: V8={V8.exists()} candidate_catalogues={candidate_files}")
    CAT = candidate_files[0]

    df = pd.read_csv(V8)
    df["trade_date"] = norm_date(df["trade_date"])
    df["reached_0_5x"], target_audit = parse_bool_series(df["reached_0_5x"], "reached_0_5x")

    canon_used = False
    if CANON.exists():
        canon = pd.read_csv(CANON)
        df = add_checkpoint_features(df, canon)
        canon_used = True

    cat = pd.read_csv(CAT)
    r = validate_candidates(df, cat)
    r = r.sort_values(["frozen_final_gate_pass","holdout_rate","holdout_n","all_rate"], ascending=[False,False,False,False])
    r.to_csv(OUT / "chronological_validation_corrected.csv", index=False)

    f = make_forensics(r)
    for name, frame in f.items():
        frame.to_csv(OUT / f"{name}.csv", index=False)

    # Explicit defect audit: compare original validator's conceptual behavior for
    # trajectory candidates (V8-only application) with corrected application.
    traj = r[r.kind.isin(["TRAJECTORY","V8_PLUS_TRAJECTORY"])].copy()
    defect_audit = {
        "trajectory_candidate_count": int(len(traj)),
        "trajectory_with_nonzero_corrected_holdout": int((traj.holdout_n > 0).sum()),
        "trajectory_with_corrected_final_pass": int(traj.frozen_final_gate_pass.sum()),
        "note": "The prior validator loaded only the V8 matrix. Trajectory candidates therefore could not be matched when their trajectory columns were absent. This corrected run reconstructs the same trajectory features used by the miner before validation."
    }
    (OUT / "trajectory_validation_defect_audit.json").write_text(json.dumps(defect_audit, indent=2), encoding="utf-8")

    summary = {
        "status":"V12_6_PHASE3A_CORRECTED_VALIDATION_COMPLETE",
        "production_modified":False,
        "exact_v8_matrix":str(V8),
        "canonical_available":canon_used,
        "candidate_count":int(len(r)),
        "v8_exact_candidates":int((r.kind=="V8_EXACT").sum()),
        "trajectory_candidates":int(r.kind.isin(["TRAJECTORY","V8_PLUS_TRAJECTORY"]).sum()),
        "holdout_research_candidates":int(((r.holdout_n>0)&(~r.frozen_final_gate_pass)).sum()),
        "final_validation_candidates":int(r.frozen_final_gate_pass.sum()),
        "max_holdout_rate":float(r.holdout_rate.max()) if r.holdout_rate.notna().any() else None,
        "target_audit":target_audit,
        "frozen_gate":{"hit_rate":GATE_RATE,"holdout_n":GATE_N,"holdout_dates":GATE_DATES,"holdout_symbols":GATE_SYMBOLS},
        "trajectory_defect_audit":defect_audit
    }
    summary["candidate_catalogue"] = str(CAT)
    (OUT / "v12_6_phase3a_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("\nFORENSICS WRITTEN:")
    for k in f:
        print(f" - {OUT / (k + '.csv')}")

if __name__ == "__main__":
    main()
