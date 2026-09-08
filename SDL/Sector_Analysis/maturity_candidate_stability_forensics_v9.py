
from pathlib import Path
import json
import pandas as pd

# Script lives in SDL\Sector_Analysis; therefore this is the SDL root.
ROOT = Path(__file__).resolve().parent
SI = ROOT / ".sector_intelligence"
V8 = SI / "maturity_conditional_pattern_discovery_v8"
ORB = SI / "smart_replay_hit_discovery" / "multi_window_outcomes.csv"
OUT = SI / "maturity_candidate_stability_forensics_v9"
OUT.mkdir(parents=True, exist_ok=True)

def norm(x):
    return str(x).strip().lower().replace(".", "_").replace("-", "_").replace(" ", "_")

def col(df, *names):
    m = {norm(c): c for c in df.columns}
    for n in names:
        if norm(n) in m:
            return m[norm(n)]
    return None

# Discover V8 candidate CSV automatically, avoiding dependence on one filename.
csvs = sorted(V8.glob("*.csv"))
if not csvs:
    raise FileNotFoundError(f"No V8 CSV output found under {V8}")

candidate_file = None
for p in csvs:
    try:
        d = pd.read_csv(p, nrows=5)
    except Exception:
        continue
    if col(d, "pattern_features", "pattern") and col(d, "hit_rate", "reached_0_5x_rate"):
        candidate_file = p
        break

if candidate_file is None:
    raise FileNotFoundError(f"No V8 candidate CSV found under {V8}")

cand = pd.read_csv(candidate_file)
pattern_col = col(cand, "pattern_features", "pattern")
rate_col = col(cand, "hit_rate", "reached_0_5x_rate")
orb_col = col(cand, "orb_minutes")
mat_col = col(cand, "maturity")
if not all([pattern_col, rate_col, orb_col, mat_col]):
    raise ValueError("V8 candidate CSV lacks required columns")

cand[rate_col] = pd.to_numeric(cand[rate_col], errors="coerce")
cand = cand[cand[rate_col] >= 0.67].copy()

orb = pd.read_csv(ORB)
om = col(orb, "orb_minutes"); sy = col(orb, "symbol"); dt = col(orb, "trade_date")
anc = col(orb, "anchor_time")
hit = col(orb, "reached_0.5x", "reached_0_5x")
if not all([om, sy, dt, anc, hit]):
    raise ValueError("ORB outcome cache lacks required fields")

orb["trade_date"] = pd.to_datetime(orb[dt], errors="coerce").dt.date
orb[hit] = pd.to_numeric(orb[hit], errors="coerce")
orb = orb[orb[hit].isin([0,1])].copy()

# V9 deliberately performs stability/holdout analysis on V8 candidates.
# It does not change the outcome definition.
results = []
for i, c in cand.reset_index(drop=True).iterrows():
    minutes = int(c[orb_col])
    maturity = str(c[mat_col])
    pattern = str(c[pattern_col])

    s = orb[orb[om] == minutes].copy()
    mt = pd.to_datetime(maturity).time()

    def anchor_ok(v):
        try:
            return pd.to_datetime(str(v)).time() <= mt
        except Exception:
            return True

    s = s[s[anc].map(anchor_ok)].copy()
    n = len(s)
    # V8 pattern fields are evidence-state expressions. We can only
    # re-evaluate them if their named fields exist in the outcome/evidence
    # data, so this V9 records stability of the candidate cohort from the
    # V8 declared sample and performs chronological holdout on that cohort.
    v8_n_col = col(cand, "n", "sample_n")
    declared_n = int(c[v8_n_col]) if v8_n_col else None
    dates = sorted(pd.to_datetime(s[dt], errors="coerce").dropna().dt.date.unique())
    # The V8 candidate itself supplies the discovered rate; V9's independent
    # holdout requires event-level reconstruction, which may not be possible
    # from the outcome cache alone. Mark that limitation rather than inventing it.
    results.append({
        "candidate_id": int(i),
        "orb_minutes": minutes,
        "maturity": maturity,
        "pattern_features": pattern,
        "v8_hit_rate": float(c[rate_col]),
        "v8_declared_n": declared_n,
        "orb_event_pool_n": n,
        "orb_event_pool_dates": len(dates),
        "classification": "HOLDOUT_REQUIRED" if float(c[rate_col]) >= 0.67 else "REJECT",
        "holdout_status": "REQUIRES_EVENT_LEVEL_EVIDENCE_RECONSTRUCTION",
    })

st = pd.DataFrame(results)
st.to_csv(OUT / "candidate_stability.csv", index=False)

summary = {
    "status": "READY",
    "cache_only": True,
    "raw_source_scan": False,
    "v8_candidates_ge_67": int(len(cand)),
    "stability_rows": int(len(st)),
    "validation_candidates": 0,
    "holdout_required": int(len(st)),
    "best_v8_hit_rate": float(st["v8_hit_rate"].max()) if len(st) else None,
    "hard_validation_gate": 0.80,
    "minimum_n": 30,
    "minimum_dates": 4,
    "note": "V9 fixed path resolution. Existing reached_0.5x is unchanged. This run does not invent event-level holdout matches when the V8 evidence-state reconstruction is unavailable; candidates remain HOLDOUT_REQUIRED until independently reconstructed."
}
(OUT / "v9_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
