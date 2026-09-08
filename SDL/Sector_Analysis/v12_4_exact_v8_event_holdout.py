from __future__ import annotations
import argparse, json, itertools
from pathlib import Path
import pandas as pd

DEFAULT_ROOT = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis")
HARD_GATE = 0.80
RESEARCH_GATE = 0.67
MIN_N = 30
MIN_DATES = 4
MIN_SYMBOLS = 10
MAX_FEATURES = 3
HOLDOUT_DATES = 6

def truth(x):
    return str(x).strip().lower() in {"true","1","yes","y","up","down"}

def semantic_group(c):
    if "dir" in c or c.endswith("agreement"):
        return "dir"
    if "state" in c and any(x in c for x in ("ce_","pe_","pec_","fut_oi")):
        return "oi"
    return c

def candidate_rows(g, min_n, min_dates):
    feature_cols = [c for c in g.columns
                    if c not in {"orb_dir","orb_minutes","maturity","symbol","trade_date","reached_0_5x"}]
    feature_cols = [c for c in feature_cols if g[c].nunique(dropna=True) <= 8]
    out = []
    base = float(g["reached_0_5x"].mean())
    for k in range(1, MAX_FEATURES + 1):
        for cols in itertools.combinations(feature_cols, k):
            if k > 1 and len({semantic_group(c) for c in cols}) < k:
                continue
            states = [g[c].dropna().astype(str).value_counts().head(5).index.tolist()
                      for c in cols]
            for combo in itertools.product(*states):
                mask = pd.Series(True, index=g.index)
                for c, v in zip(cols, combo):
                    mask &= g[c].astype(str).eq(v)
                h = g.loc[mask]
                n = len(h)
                dates = h["trade_date"].nunique()
                if n < min_n or dates < min_dates:
                    continue
                rate = float(h["reached_0_5x"].mean())
                out.append({
                    "orb_minutes": int(g["orb_minutes"].iloc[0]),
                    "maturity": str(g["maturity"].iloc[0]),
                    "pattern_features": " & ".join(f"{c}={v}" for c,v in zip(cols,combo)),
                    "n_train": n,
                    "dates_train": dates,
                    "symbols_train": h["symbol"].nunique(),
                    "train_hit_rate": rate,
                    "train_base_rate": base,
                    "train_lift": rate-base,
                })
    if not out:
        return pd.DataFrame()
    return pd.DataFrame(out).drop_duplicates(
        ["orb_minutes","maturity","pattern_features"]
    )

def apply_pattern(df, expression):
    mask = pd.Series(True, index=df.index)
    for part in expression.split(" & "):
        c, v = part.split("=", 1)
        if c not in df.columns:
            return df.iloc[0:0]
        mask &= df[c].astype(str).eq(v)
    return df.loc[mask]

def main():
    ap = argparse.ArgumentParser(description="V12.4 exact-V8 feature-matrix event-level holdout.")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--holdout-dates", type=int, default=HOLDOUT_DATES)
    ap.add_argument("--min-n", type=int, default=MIN_N)
    ap.add_argument("--min-dates", type=int, default=MIN_DATES)
    a = ap.parse_args()

    root = Path(a.root)
    intel = root / ".sector_intelligence"
    src = intel / "maturity_conditional_pattern_discovery_v8" / "maturity_feature_matrix.csv"
    out = intel / "v12_4_exact_v8_event_holdout"
    out.mkdir(parents=True, exist_ok=True)

    summary = {
        "status":"FAILED",
        "study":"V12_4_EXACT_V8_EVENT_LEVEL_HOLDOUT",
        "source":str(src),
        "production_changes":False,
        "authoritative_target":"reached_0_5x",
        "fixed_0_5_percent_target_used":False,
        "candidate_semantics":"exact V8 maturity_feature_matrix; no reconstruction",
        "hard_gate":HARD_GATE,
        "research_gate":RESEARCH_GATE,
        "min_train_n":a.min_n,
        "min_train_dates":a.min_dates,
        "min_holdout_symbols_for_final":MIN_SYMBOLS,
    }
    if not src.exists():
        summary["reason"]="V8 maturity_feature_matrix.csv not found"
        (out/"v12_4_summary.json").write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2)); return 2

    df = pd.read_csv(src, low_memory=False)
    required = {"orb_minutes","maturity","symbol","trade_date","reached_0_5x"}
    missing = sorted(required - set(df.columns))
    if missing:
        summary["reason"]="Missing fields: "+", ".join(missing)
        (out/"v12_4_summary.json").write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2)); return 3

    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
    df["reached_0_5x"] = df["reached_0_5x"].map(truth)
    df = df[df["trade_date"].notna()].copy()
    dates = sorted(df["trade_date"].unique())
    if len(dates) <= a.holdout_dates:
        summary["reason"]="Insufficient distinct dates for train/holdout split"
        (out/"v12_4_summary.json").write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2)); return 4

    train_dates = dates[:-a.holdout_dates]
    holdout_dates = dates[-a.holdout_dates:]
    train = df[df.trade_date.isin(train_dates)].copy()
    holdout = df[df.trade_date.isin(holdout_dates)].copy()

    candidate_parts = []
    for key, g in train.groupby(["orb_minutes","maturity"], sort=True):
        if len(g) >= a.min_n and g.trade_date.nunique() >= a.min_dates:
            c = candidate_rows(g, a.min_n, a.min_dates)
            if not c.empty:
                candidate_parts.append(c)
    cand = pd.concat(candidate_parts, ignore_index=True) if candidate_parts else pd.DataFrame()
    if cand.empty:
        summary.update({
            "reason":"No train candidates",
            "total_dates":len(dates),
            "train_dates":len(train_dates),
            "holdout_dates":len(holdout_dates),
        })
        (out/"v12_4_summary.json").write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2)); return 0

    # Only candidates that meet the research gate on TRAIN proceed to holdout.
    cand = cand[cand["train_hit_rate"] >= RESEARCH_GATE].copy()
    cand = cand.sort_values(["train_hit_rate","dates_train","n_train"],
                            ascending=[False,False,False])
    cand.to_csv(out/"train_candidates_ge_67.csv", index=False)

    results = []
    for _, row in cand.iterrows():
        h = holdout[(holdout["orb_minutes"] == row["orb_minutes"]) &
                    (holdout["maturity"] == row["maturity"])]
        h = apply_pattern(h, row["pattern_features"])
        n = len(h)
        dates_h = h["trade_date"].nunique()
        symbols_h = h["symbol"].nunique()
        rate = float(h["reached_0_5x"].mean()) if n else None
        results.append({
            **row.to_dict(),
            "n_holdout":n,
            "dates_holdout":dates_h,
            "symbols_holdout":symbols_h,
            "holdout_hit_rate":rate,
            "holdout_classification":(
                "FINAL_VALIDATION" if rate is not None and rate >= HARD_GATE
                and n >= MIN_N and dates_h >= 3 and symbols_h >= MIN_SYMBOLS
                else "OPTIMIZATION_RESEARCH" if rate is not None and rate >= RESEARCH_GATE
                else "NOT_VALIDATED"
            )
        })

    res = pd.DataFrame(results)
    res.to_csv(out/"independent_holdout_results.csv", index=False)
    final = res[res["holdout_classification"]=="FINAL_VALIDATION"].copy()
    research = res[res["holdout_classification"]=="OPTIMIZATION_RESEARCH"].copy()
    final.to_csv(out/"final_validation_candidates.csv", index=False)
    research.to_csv(out/"holdout_research_candidates.csv", index=False)

    summary.update({
        "status":"READY",
        "total_dates":len(dates),
        "train_dates":len(train_dates),
        "holdout_dates":len(holdout_dates),
        "train_date_start":str(train_dates[0]),
        "train_date_end":str(train_dates[-1]),
        "holdout_date_start":str(holdout_dates[0]),
        "holdout_date_end":str(holdout_dates[-1]),
        "v8_exact_feature_rows":len(df),
        "train_rows":len(train),
        "holdout_rows":len(holdout),
        "train_candidates_ge_67":len(cand),
        "holdout_evaluated":len(res),
        "final_validation_candidates":len(final),
        "holdout_research_candidates":len(research),
        "max_holdout_rate":float(res["holdout_hit_rate"].max()) if res["holdout_hit_rate"].notna().any() else None,
        "population_reconciliation":"exact V8 feature matrix; no reconstructed semantics",
    })
    (out/"v12_4_summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
