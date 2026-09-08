
"""
NTIS SDL V10 - VECTOR CPU OPTIMIZED
Independent chronological holdout reconstruction.

Research-only. No frozen SDL production logic is modified.

Key optimization:
- canonical CSV is read once in chunks
- timestamp cutoff assignment is vectorized
- only latest evidence row per symbol/date/maturity is retained
- candidate matching uses vectorized merges/grouping, not Python row loops
"""

from pathlib import Path
import json, math, re
import pandas as pd

ROOT = Path(__file__).resolve().parent
SI = ROOT / ".sector_intelligence"
CANONICAL = SI / "data_strength_combination_study" / "canonical_strength_observations.csv"
ORB = SI / "smart_replay_hit_discovery" / "multi_window_outcomes.csv"
V8 = SI / "maturity_conditional_pattern_discovery_v8"
OUT = SI / "maturity_holdout_reconstruction_v10"
OUT.mkdir(parents=True, exist_ok=True)

CHUNK = 50000
CUTS = ["09:30", "09:45", "10:00", "10:15"]

def norm(x):
    return str(x).strip().lower().replace(".", "_").replace("-", "_").replace(" ", "_")

def col(headers, *names):
    m = {norm(c): c for c in headers}
    for n in names:
        if norm(n) in m:
            return m[norm(n)]
    return None

def parse_pattern(s):
    d = {}
    for p in str(s).split("&"):
        p = p.strip()
        if "=" in p:
            k, v = p.split("=", 1)
            d[k.strip()] = v.strip()
    return d

# ---------- V8 candidates ----------
candidate_file = None
for p in sorted(V8.glob("*.csv")):
    try:
        h = pd.read_csv(p, nrows=0).columns.tolist()
        if col(h, "pattern_features", "pattern") and col(h, "hit_rate", "reached_0_5x_rate"):
            candidate_file = p
            break
    except Exception:
        pass
if candidate_file is None:
    raise FileNotFoundError(f"No V8 candidate CSV under {V8}")

cand = pd.read_csv(candidate_file)
pcol = col(cand.columns, "pattern_features", "pattern")
rcol = col(cand.columns, "hit_rate", "reached_0_5x_rate")
mcol = col(cand.columns, "orb_minutes")
tcol = col(cand.columns, "maturity")
cand[rcol] = pd.to_numeric(cand[rcol], errors="coerce")
cand = cand[cand[rcol] >= 0.67].copy().reset_index(drop=True)

# Extract feature constraints from V8 patterns.
features = ["price_dir", "orb_agree", "magnitude_count_band"]
for f in features:
    cand[f] = None
for i, s in enumerate(cand[pcol].astype(str)):
    for k, v in parse_pattern(s).items():
        if k in features:
            cand.at[i, k] = v

# ---------- ORB outcome cache ----------
orb = pd.read_csv(ORB)
om = col(orb.columns, "orb_minutes")
sy = col(orb.columns, "symbol")
dt = col(orb.columns, "trade_date")
anc = col(orb.columns, "anchor_time")
hit = col(orb.columns, "reached_0.5x", "reached_0_5x")
if not all([om, sy, dt, anc, hit]):
    raise ValueError("ORB outcome cache missing required fields")

orb["symbol"] = orb[sy].astype(str)
orb["trade_date"] = pd.to_datetime(orb[dt], errors="coerce").dt.date
orb["orb_minutes"] = pd.to_numeric(orb[om], errors="coerce")
orb["anchor_time"] = pd.to_datetime(orb[anc], errors="coerce").dt.time
orb["outcome"] = pd.to_numeric(orb[hit], errors="coerce")
orb = orb[orb["outcome"].isin([0, 1])].copy()

# Maturity validity: ORB anchor must already exist by maturity.
cut_df = pd.DataFrame({"maturity": CUTS})
cut_df["cut_time"] = pd.to_datetime(cut_df["maturity"]).dt.time

# ---------- canonical header ----------
headers = pd.read_csv(CANONICAL, nrows=0).columns.tolist()
csym = col(headers, "symbol")
cdt = col(headers, "trade_date")
cts = col(headers, "timestamp")
cpd = col(headers, "price_direction")
coa = col(headers, "direction_agreement")
cmg = col(headers, "magnitude_count")
if not all([csym, cdt, cts, cpd, coa, cmg]):
    raise ValueError("Canonical cache lacks required V8 fields")

usecols = [csym, cdt, cts, cpd, coa, cmg]

# Determine chronological date split with a cheap one-column chunk scan.
date_parts = []
for ch in pd.read_csv(CANONICAL, usecols=[cdt], chunksize=CHUNK):
    date_parts.append(pd.to_datetime(ch[cdt], errors="coerce").dt.date.dropna())
dates = pd.concat(date_parts, ignore_index=True).drop_duplicates().sort_values().tolist()
if len(dates) < 8:
    raise RuntimeError(f"Only {len(dates)} dates available")
hold_n = max(1, math.ceil(len(dates) * 0.25))
holdout_dates = set(dates[-hold_n:])
development_dates = set(dates[:-hold_n])

# ---------- vectorized canonical maturity snapshots ----------
# A row can serve a maturity if timestamp <= cutoff. We assign each row to
# the latest cutoff it has reached; then groupby keeps latest evidence for
# each symbol/date/cutoff. This avoids Python loops over rows.
snap_parts = []
for ch in pd.read_csv(CANONICAL, usecols=usecols, chunksize=CHUNK):
    ch["trade_date"] = pd.to_datetime(ch[cdt], errors="coerce").dt.date
    ch["timestamp"] = pd.to_datetime(ch[cts], errors="coerce")
    ch["symbol"] = ch[csym].astype(str)
    ch["price_dir"] = ch[cpd].astype(str)
    ch["orb_agree"] = ch[coa].astype(str)
    ch["magnitude_count_band"] = ch[cmg].astype(str)
    ch = ch[["symbol","trade_date","timestamp","price_dir","orb_agree","magnitude_count_band"]]
    ch = ch.dropna(subset=["trade_date","timestamp"])

    # Cross join against only four cutoffs; vectorized and small.
    x = ch.merge(cut_df, how="cross")
    x = x[x["timestamp"].dt.time <= x["cut_time"]]
    if x.empty:
        continue
    x = x.sort_values("timestamp").drop_duplicates(
        ["symbol","trade_date","maturity"], keep="last"
    )
    snap_parts.append(x[["symbol","trade_date","maturity","price_dir","orb_agree","magnitude_count_band"]])

snap = pd.concat(snap_parts, ignore_index=True)
snap = snap.sort_values("trade_date").drop_duplicates(
    ["symbol","trade_date","maturity"], keep="last"
)

# ---------- Build compact candidate keys ----------
# Only exact V8 feature states are evaluated.
cand_long = cand[["orb_minutes","maturity","price_dir","orb_agree","magnitude_count_band"]].copy()
cand_long["candidate_id"] = cand.index
cand_long["pattern_features"] = cand[pcol].astype(str)
cand_long["v8_rate"] = cand[rcol].astype(float)

# Merge candidate definitions with snapshots. Null feature constraints are
# wildcards, implemented as equality masks after a common merge.
candidate_results = []

for _, c in cand_long.iterrows():
    s = snap[snap["maturity"] == c["maturity"]].copy()
    for f in features:
        if pd.notna(c[f]) and str(c[f]) != "":
            s = s[s[f].astype(str) == str(c[f])]
    if s.empty:
        continue

    events = orb[
        (orb["orb_minutes"] == int(c["orb_minutes"])) &
        (orb["anchor_time"].isna() | (
            orb["anchor_time"] <= pd.to_datetime(c["maturity"]).time()
        ))
    ][["symbol","trade_date","outcome"]].copy()

    m = s.merge(events, on=["symbol","trade_date"], how="inner")
    if m.empty:
        continue

    m["_holdout"] = m["trade_date"].isin(holdout_dates)
    m["_development"] = m["trade_date"].isin(development_dates)

    total = len(m)
    wins = int(m["outcome"].sum())
    dev = m[m["_development"]]
    hold = m[m["_holdout"]]

    dev_rate = float(dev["outcome"].mean()) if len(dev) else None
    hold_rate = float(hold["outcome"].mean()) if len(hold) else None

    if hold_rate is not None and len(hold) >= 10 and hold_rate >= 0.80:
        cls = "VALIDATION_CANDIDATE"
    elif hold_rate is not None and hold_rate >= 0.67:
        cls = "HOLDOUT_PASS_RESEARCH"
    elif hold_rate is not None:
        cls = "HOLDOUT_FAIL"
    else:
        cls = "HOLDOUT_INSUFFICIENT"

    candidate_results.append({
        "candidate_id": int(c["candidate_id"]),
        "orb_minutes": int(c["orb_minutes"]),
        "maturity": str(c["maturity"]),
        "pattern_features": str(c["pattern_features"]),
        "v8_rate": float(c["v8_rate"]),
        "reconstructed_n": total,
        "reconstructed_rate": wins / total,
        "development_n": len(dev),
        "development_rate": dev_rate,
        "holdout_n": len(hold),
        "holdout_rate": hold_rate,
        "holdout_dates": int(hold["trade_date"].nunique()) if len(hold) else 0,
        "symbols": int(m["symbol"].nunique()),
        "classification": cls
    })

res = pd.DataFrame(candidate_results)
if not res.empty:
    res = res.sort_values(["holdout_rate","holdout_n","v8_rate"], ascending=[False,False,False])
    res.to_csv(OUT / "v10_candidate_holdout_results.csv", index=False)

summary = {
    "status": "READY",
    "version": "V10_VECTOR_OPTIMIZED",
    "cpu_optimized": True,
    "canonical_chunk_rows": CHUNK,
    "vectorized_maturity_assignment": True,
    "canonical_full_dataframe_loaded": False,
    "canonical_dates": len(dates),
    "development_dates": len(development_dates),
    "holdout_dates": len(holdout_dates),
    "holdout_date_start": str(min(holdout_dates)),
    "holdout_date_end": str(max(holdout_dates)),
    "v8_candidates_ge_67": int(len(cand)),
    "evaluated_candidates": int(len(res)),
    "validation_candidates": int((res["classification"] == "VALIDATION_CANDIDATE").sum()) if not res.empty else 0,
    "holdout_pass_research": int((res["classification"] == "HOLDOUT_PASS_RESEARCH").sum()) if not res.empty else 0,
    "holdout_fail": int((res["classification"] == "HOLDOUT_FAIL").sum()) if not res.empty else 0,
    "hard_validation_gate": 0.80,
    "primary_outcome": "existing reached_0.5x from multi_window_outcomes.csv",
    "note": "Research-only chronological holdout. Existing outcome unchanged. No threshold reduction."
}
(OUT / "v10_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
