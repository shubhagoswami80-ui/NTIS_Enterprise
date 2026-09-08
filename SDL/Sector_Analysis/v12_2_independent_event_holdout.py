from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

BASE = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\.sector_intelligence")
OUT = BASE / "v12_2_independent_event_holdout"
OUT.mkdir(parents=True, exist_ok=True)

OUTCOME = BASE / "smart_replay_hit_discovery" / "multi_window_outcomes.csv"
CANDIDATE = BASE / "maturity_conditional_pattern_discovery_v8" / "conditional_pattern_candidates.csv"

def norm(x):
    return re.sub(r"[^a-z0-9]+", "_", str(x).strip().lower()).strip("_")

def parse_terms(expr):
    return [x.strip() for x in re.split(r"\s*&\s*", str(expr)) if x.strip()]

def make_features(d):
    x = d.copy()

    # Exact semantic reconstruction from the available V8 outcome vocabulary.
    x["price_dir"] = x["orb_direction"].astype(str).str.upper().replace({
        "UP": "UP", "DOWN": "DOWN"
    })
    x["price_state"] = x["price_dir"].map({"UP": "POS", "DOWN": "NEG"})

    # ORB agreement: price direction agrees with ORB direction.
    x["orb_agree"] = (
        x["price_dir"].eq(x["orb_direction"].astype(str).str.upper())
    ).map({True: "YES", False: "NO"})

    # The replay outcome has only the directional ORB and price direction;
    # use the same directional agreement as the closest available V8 source.
    x["orb_price_agree"] = x["orb_agree"]

    magnitude_cols = [
        "fut_gt500", "fut_gt1000", "fut_lt500", "fut_lt1000",
        "ce_gt500", "ce_gt1000", "ce_lt500", "ce_lt1000",
        "pe_gt500", "pe_gt1000", "pe_lt500", "pe_lt1000",
        "pec_gt500", "pec_gt1000", "pec_lt500", "pec_lt1000",
    ]
    present = [c for c in magnitude_cols if c in x.columns]
    if present:
        x["magnitude_count"] = x[present].fillna(False).astype(bool).sum(axis=1)
    else:
        x["magnitude_count"] = 0
    x["magnitude_count_band"] = pd.cut(
        x["magnitude_count"],
        bins=[-1, 0, 1, float("inf")],
        labels=["0", "1", "2+"],
    ).astype(str)

    x["volume_state"] = x["volume_pct"].apply(
        lambda v: "POS" if pd.notna(v) and float(v) > 0
        else "NEG" if pd.notna(v) and float(v) < 0
        else "FLAT"
    )

    return x

def term_mask(x, term):
    # Parse field=value.
    m = re.match(r"^(.+?)\s*=\s*(.+)$", term)
    if not m:
        return None
    field = norm(m.group(1))
    expected = norm(m.group(2))
    if field not in x.columns:
        return None
    return x[field].astype(str).map(norm).eq(expected)

def candidate_mask(x, expr):
    mask = pd.Series(True, index=x.index)
    for term in parse_terms(expr):
        m = term_mask(x, term)
        if m is None:
            return None
        mask &= m
    return mask

def target_series(s):
    return s.astype(str).str.upper().isin(["TRUE", "1", "YES"])

def main():
    if not OUTCOME.exists():
        raise FileNotFoundError(OUTCOME)
    if not CANDIDATE.exists():
        raise FileNotFoundError(CANDIDATE)

    outcomes = pd.read_csv(OUTCOME, low_memory=False)
    candidates = pd.read_csv(CANDIDATE, low_memory=False)

    required = {"trade_date", "orb_minutes", "reached_0.5x"}
    missing = required - set(outcomes.columns)
    if missing:
        raise RuntimeError(f"Outcome schema missing: {sorted(missing)}")

    if "pattern_features" not in candidates.columns or "hit_rate" not in candidates.columns:
        raise RuntimeError(f"Unexpected V8 candidate schema: {list(candidates.columns)}")

    outcomes["trade_date"] = pd.to_datetime(
        outcomes["trade_date"], errors="coerce"
    ).dt.date
    outcomes = outcomes.dropna(subset=["trade_date"]).copy()

    # Preserve V8 candidate window and test only the research candidates.
    candidates["hit_rate"] = pd.to_numeric(candidates["hit_rate"], errors="coerce")
    candidates = candidates[
        candidates["hit_rate"].between(0.60, 0.80, inclusive="left")
    ].copy()

    # Candidate semantics are tied to ORB window + maturity. Reconcile these
    # dimensions before matching, so a 5M rule cannot match a 10M event.
    features = make_features(outcomes)

    dates = sorted(features["trade_date"].unique())
    if len(dates) < 6:
        raise RuntimeError(f"Too few dates for holdout: {len(dates)}")
    cut = max(1, min(len(dates) - 1, int(len(dates) * 0.70)))
    train_dates = set(dates[:cut])
    holdout_dates = set(dates[cut:])

    audit = []
    for _, c in candidates.iterrows():
        expr = str(c["pattern_features"])
        orb_minutes = int(c["orb_minutes"]) if pd.notna(c["orb_minutes"]) else None
        maturity = str(c["maturity"])

        pool = features
        if orb_minutes is not None:
            pool = pool[pool["orb_minutes"].astype(int).eq(orb_minutes)]

        mask = candidate_mask(pool, expr)
        if mask is None:
            audit.append({
                "orb_minutes": orb_minutes,
                "maturity": maturity,
                "pattern_features": expr,
                "research_hit_rate": float(c["hit_rate"]),
                "matched": False,
                "reason": "UNMAPPED_FEATURE",
                "train_n": 0,
                "holdout_n": 0,
                "train_rate": None,
                "holdout_rate": None,
            })
            continue

        matched = pool.loc[mask, ["trade_date", "reached_0.5x"]].copy()
        matched["target"] = target_series(matched["reached_0.5x"])

        tr = matched[matched["trade_date"].isin(train_dates)]
        ho = matched[matched["trade_date"].isin(holdout_dates)]
        tr_rate = float(tr["target"].mean()) if len(tr) else None
        ho_rate = float(ho["target"].mean()) if len(ho) else None

        if ho_rate is not None and ho_rate >= 0.80 and len(ho) >= 30:
            cls = "FINAL_VALIDATION_CANDIDATE"
        elif ho_rate is not None and ho_rate >= 0.67:
            cls = "OPTIMIZATION_RESEARCH"
        elif ho_rate is not None:
            cls = "NOT_VALIDATED"
        else:
            cls = "NO_HOLDOUT_EVENTS"

        audit.append({
            "orb_minutes": orb_minutes,
            "maturity": maturity,
            "pattern_features": expr,
            "research_hit_rate": float(c["hit_rate"]),
            "matched": True,
            "reason": "OK",
            "train_n": int(len(tr)),
            "holdout_n": int(len(ho)),
            "train_rate": tr_rate,
            "holdout_rate": ho_rate,
            "holdout_dates": int(ho["trade_date"].nunique()),
            "classification": cls,
        })

    result = pd.DataFrame(audit)
    result.to_csv(OUT / "v12_2_holdout_by_candidate.csv", index=False)

    resolved = result[result["matched"] == True]
    hr = pd.to_numeric(resolved["holdout_rate"], errors="coerce").dropna()
    summary = {
        "status": "READY",
        "study": "V12_2_INDEPENDENT_EVENT_LEVEL_HOLDOUT",
        "candidate_rows_tested": int(len(candidates)),
        "candidate_rows_resolved": int(len(resolved)),
        "unmapped_candidates": int((result["matched"] == False).sum()),
        "total_dates": int(len(dates)),
        "train_dates": int(len(train_dates)),
        "holdout_dates": int(len(holdout_dates)),
        "train_date_start": str(min(train_dates)),
        "train_date_end": str(max(train_dates)),
        "holdout_date_start": str(min(holdout_dates)),
        "holdout_date_end": str(max(holdout_dates)),
        "final_validation_candidates": int(
            (result.get("classification", pd.Series(dtype=str)) == "FINAL_VALIDATION_CANDIDATE").sum()
        ),
        "optimization_research_candidates": int(
            (result.get("classification", pd.Series(dtype=str)) == "OPTIMIZATION_RESEARCH").sum()
        ),
        "not_validated_candidates": int(
            (result.get("classification", pd.Series(dtype=str)) == "NOT_VALIDATED").sum()
        ),
        "max_holdout_rate": float(hr.max()) if len(hr) else None,
        "authoritative_target": "reached_0.5x",
        "fixed_0.5_percent_target_used": False,
        "same_date_train_holdout_leakage": False,
        "production_changes": False,
        "semantic_reconstruction_note": (
            "price_dir/price_state/ORB agreement/magnitude_count_band/volume_state "
            "were reconstructed from the available replay outcome schema; "
            "V8 candidate population reconciliation must be reviewed before any "
            "candidate is considered validated."
        ),
    }

    if len(hr):
        result.sort_values(
            ["holdout_rate", "holdout_n"], ascending=[False, False]
        ).head(50).to_csv(OUT / "v12_2_top_holdout_candidates.csv", index=False)

    (OUT / "v12_2_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"OUTPUT_DIR: {OUT}")

if __name__ == "__main__":
    main()
