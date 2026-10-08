from pathlib import Path
import pandas as pd
import json

ROOT = Path(".sector_intelligence/v12_6_exhaustive_research")
VAL = ROOT / "chronological_validation_corrected.csv"
OUT = ROOT

if not VAL.exists():
    raise FileNotFoundError(f"Missing {VAL}")

df = pd.read_csv(VAL)

# Normalize numeric columns defensively.
for c in ["holdout_n","holdout_dates","holdout_symbols","holdout_rate","factor_count"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

supported = df[df["holdout_n"] > 0].copy()
robust = supported[
    (supported["holdout_n"] >= 30) &
    (supported["holdout_dates"] >= 3) &
    (supported["holdout_symbols"] >= 10)
].copy()

# 1. Support gates
support = pd.DataFrame([
    ["holdout_n >= 30", int((supported.holdout_n >= 30).sum())],
    ["holdout_dates >= 3", int((supported.holdout_dates >= 3).sum())],
    ["holdout_symbols >= 10", int((supported.holdout_symbols >= 10).sum())],
    ["all three", int(len(robust))]
], columns=["criterion","candidate_count"])
support.to_csv(OUT / "phase3b_support_summary.csv", index=False)

# 2. Rate distribution
bins = [-1, .50, .60, .65, .70, .75, .80, 1.01]
labels = ["<50%","50-<60%","60-<65%","65-<70%","70-<75%","75-<80%",">=80%"]
rb = supported.copy()
rb["rate_band"] = pd.cut(rb.holdout_rate, bins=bins, labels=labels, right=False)
rate = rb.groupby("rate_band", observed=False).size().rename("candidate_count").reset_index()
rate.to_csv(OUT / "phase3b_rate_distribution.csv", index=False)

# 3. Family and factor-count analysis
family = supported.groupby("kind").agg(
    candidates=("candidate_id","size"),
    max_rate=("holdout_rate","max"),
    median_rate=("holdout_rate","median"),
    n_ge30=("holdout_n",lambda x:int((x>=30).sum())),
    n_robust=("candidate_id",lambda x:int(x.isin(robust.candidate_id).sum()))
).reset_index()
family.to_csv(OUT / "phase3b_family_summary.csv", index=False)

fc = supported.groupby(["kind","factor_count"], dropna=False).agg(
    candidates=("candidate_id","size"),
    max_rate=("holdout_rate","max"),
    median_rate=("holdout_rate","median"),
    n_ge30=("holdout_n",lambda x:int((x>=30).sum())),
    n_robust=("candidate_id",lambda x:int(x.isin(robust.candidate_id).sum()))
).reset_index()
fc.to_csv(OUT / "phase3b_factor_count_summary.csv", index=False)

# 4. Concentration of robust candidates.
# These are descriptive, using fields already produced by the corrected validator.
conc = robust[[
    "candidate_id","kind","factor_count","factors","states",
    "holdout_n","holdout_good_n","holdout_bad_n","holdout_rate",
    "holdout_dates","holdout_symbols",
    "top_holdout_date_share","top_holdout_symbol_share"
]].sort_values(["holdout_rate","holdout_n"], ascending=[False,False])
conc.to_csv(OUT / "phase3b_robust_population.csv", index=False)

# 5. Small shortlist only for human inspection: strongest candidates
# among the robust population. This is NOT a strategy-selection file.
short = conc.head(50)
short.to_csv(OUT / "phase3b_top50_robust_for_review.csv", index=False)

summary = {
    "status":"V12_6_PHASE3B_LIGHT_FORENSICS_COMPLETE",
    "production_modified":False,
    "total_candidates":int(len(df)),
    "holdout_supported":int(len(supported)),
    "robust_by_frozen_support":int(len(robust)),
    "max_holdout_rate":float(supported.holdout_rate.max()) if len(supported) else None,
    "robust_max_holdout_rate":float(robust.holdout_rate.max()) if len(robust) else None,
    "robust_ge80":int((robust.holdout_rate >= .80).sum()),
    "interpretation_rule":"Descriptive population forensics only; no threshold optimization and no strategy selection.",
    "outputs":[
        "phase3b_support_summary.csv",
        "phase3b_rate_distribution.csv",
        "phase3b_family_summary.csv",
        "phase3b_factor_count_summary.csv",
        "phase3b_robust_population.csv",
        "phase3b_top50_robust_for_review.csv"
    ]
}
(OUT / "v12_6_phase3b_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
print("\nPHASE 3B COMPLETE — LIGHTWEIGHT POPULATION FORENSICS")
for x in summary["outputs"]:
    print(" -", OUT / x)
