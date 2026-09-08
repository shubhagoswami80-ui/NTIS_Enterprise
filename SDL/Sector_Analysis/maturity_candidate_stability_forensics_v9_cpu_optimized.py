
"""
NTIS SDL V9 CPU-OPTIMIZED
Research-only. No frozen SDL production logic changes.

Optimization:
- Reads only V8 candidate CSV + small ORB outcome cache.
- Does NOT load the 360k-row canonical evidence cache.
- Does not build symbol/date maturity snapshots.
- Does not run repeated full-data pandas merges.
- Uses one cached ORB pool per ORB window and lightweight group calculations.
- Explicitly reports that independent event-level holdout reconstruction requires
  a separate evidence-state dataset; it does not fabricate one.
"""

from pathlib import Path
import json
import csv
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
SI = ROOT / ".sector_intelligence"
V8 = SI / "maturity_conditional_pattern_discovery_v8"
ORB = SI / "smart_replay_hit_discovery" / "multi_window_outcomes.csv"
OUT = SI / "maturity_candidate_stability_forensics_v9_cpu_optimized"
OUT.mkdir(parents=True, exist_ok=True)

def norm(x):
    return str(x).strip().lower().replace(".", "_").replace("-", "_").replace(" ", "_")

def pick(headers, *names):
    m = {norm(h): h for h in headers}
    for n in names:
        if norm(n) in m:
            return m[norm(n)]
    return None

# Find V8 candidate file without reading the whole file repeatedly.
candidate_file = None
for p in sorted(V8.glob("*.csv")):
    try:
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            headers = next(csv.reader(f))
        if pick(headers, "pattern_features", "pattern") and pick(headers, "hit_rate", "reached_0_5x_rate"):
            candidate_file = p
            break
    except (OSError, StopIteration):
        continue

if candidate_file is None:
    raise FileNotFoundError(f"No V8 candidate CSV found under {V8}")

# Read only the V8 candidate rows that are >=67%.
with candidate_file.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames or []
    rate_h = pick(headers, "hit_rate", "reached_0_5x_rate")
    pattern_h = pick(headers, "pattern_features", "pattern")
    orb_h = pick(headers, "orb_minutes")
    mat_h = pick(headers, "maturity")
    n_h = pick(headers, "n", "sample_n")
    candidates = []
    for i, row in enumerate(reader):
        try:
            rate = float(row[rate_h])
        except (TypeError, ValueError):
            continue
        if rate >= 0.67:
            candidates.append({
                "candidate_id": i,
                "orb_minutes": int(float(row[orb_h])),
                "maturity": str(row[mat_h]),
                "pattern_features": str(row[pattern_h]),
                "v8_hit_rate": rate,
                "v8_declared_n": int(float(row[n_h])) if n_h and row.get(n_h) not in ("", None) else None,
            })

# Read the small ORB outcome cache once and aggregate by ORB window/date.
orb_groups = defaultdict(lambda: {"n": 0, "hits": 0, "dates": set()})
with ORB.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    h = reader.fieldnames or []
    om_h = pick(h, "orb_minutes")
    dt_h = pick(h, "trade_date")
    hit_h = pick(h, "reached_0.5x", "reached_0_5x")
    anc_h = pick(h, "anchor_time")
    if not all([om_h, dt_h, hit_h, anc_h]):
        raise ValueError("ORB outcome cache lacks required fields")

    for row in reader:
        try:
            om = int(float(row[om_h]))
            hit = int(float(row[hit_h]))
        except (TypeError, ValueError):
            continue
        if hit not in (0, 1):
            continue
        # We only need the event pool for the candidate's ORB window.
        g = orb_groups[om]
        g["n"] += 1
        g["hits"] += hit
        g["dates"].add(str(row[dt_h]))

# No repeated merges/scans. Stability status is deliberately conservative.
results = []
for c in candidates:
    pool = orb_groups.get(c["orb_minutes"], {"n": 0, "hits": 0, "dates": set()})
    pool_rate = pool["hits"] / pool["n"] if pool["n"] else None

    # V8 already established the candidate evidence-state rate. The ORB pool
    # is contextual only; it must NOT replace the V8 conditional rate.
    classification = "HOLDOUT_REQUIRED"

    results.append({
        **c,
        "orb_event_pool_n": pool["n"],
        "orb_event_pool_dates": len(pool["dates"]),
        "orb_pool_base_rate": pool_rate,
        "classification": classification,
        "holdout_status": "REQUIRES_EVENT_LEVEL_EVIDENCE_RECONSTRUCTION",
    })

out_csv = OUT / "candidate_stability.csv"
if results:
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

best = max((r["v8_hit_rate"] for r in results), default=None)
summary = {
    "status": "READY",
    "cpu_optimized": True,
    "cache_only": True,
    "raw_source_scan": False,
    "v8_candidates_ge_67": len(candidates),
    "stability_rows": len(results),
    "validation_candidates": 0,
    "holdout_required": len(results),
    "best_v8_hit_rate": best,
    "hard_validation_gate": 0.80,
    "minimum_n": 30,
    "minimum_dates": 4,
    "canonical_cache_loaded": False,
    "note": "CPU-optimized V9. The 360k-row canonical cache is intentionally not loaded because independent event-level holdout reconstruction is not supported by the current V8 candidate cache alone. No holdout rate is invented."
}
(OUT / "v9_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
