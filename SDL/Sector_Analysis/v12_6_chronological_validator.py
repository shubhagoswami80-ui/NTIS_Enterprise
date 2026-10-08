"""
NTIS SDL V12.6 — Chronological Exhaustive Validator
Research-only. Consumes candidate_catalog.csv and the exact V8 matrix.

Validation design:
- Discovery period: 2026-08-14 through 2026-08-28
- Frozen holdout period: 2026-08-31 through 2026-09-04
- Final gate remains:
  hit rate >= 80%
  holdout n >= 30
  holdout dates >= 3
  holdout symbols >= 10

Also reports:
- all-period rate
- train rate
- holdout rate
- date/symbol concentration
- recurrence
- whether a candidate has holdout support
- candidate source kind
No candidate is promoted merely because its all-period rate is high.
"""

from pathlib import Path
import json
import pandas as pd

BASE = Path(".")
V8 = BASE / ".sector_intelligence" / "maturity_conditional_pattern_discovery_v8" / "maturity_feature_matrix.csv"
CAT = BASE / ".sector_intelligence" / "v12_6_exhaustive_research" / "candidate_catalog.csv"
OUT = BASE / ".sector_intelligence" / "v12_6_exhaustive_research"

TRAIN_START = pd.Timestamp("2026-08-14").date()
TRAIN_END = pd.Timestamp("2026-08-28").date()
HOLD_START = pd.Timestamp("2026-08-31").date()
HOLD_END = pd.Timestamp("2026-09-04").date()

GATE_RATE = 0.80
GATE_N = 30
GATE_DATES = 3
GATE_SYMBOLS = 10

def parse_candidate(c):
    # candidate_id: KIND|factor=value|factor=value
    parts = str(c).split("|")
    kind = parts[0]
    pairs = {}
    for p in parts[1:]:
        if "=" in p:
            k,v = p.split("=",1)
            pairs[k] = v
    return kind, pairs

def apply_candidate(df, kind, pairs):
    mask = pd.Series(True, index=df.index)
    for col, val in pairs.items():
        if col not in df.columns:
            return df.iloc[0:0]
        if val == "<MISSING>":
            mask &= df[col].isna()
        else:
            mask &= df[col].astype(str).eq(val)
    return df[mask]

def stats(g):
    if g.empty:
        return dict(n=0, good_n=0, bad_n=0, rate=None, dates=0, symbols=0)
    y = g["reached_0_5x"].astype(bool)
    return dict(
        n=int(len(g)),
        good_n=int(y.sum()),
        bad_n=int((~y).sum()),
        rate=float(y.mean()),
        dates=int(g.trade_date.nunique()),
        symbols=int(g.symbol.nunique()),
    )

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not V8.exists():
        raise FileNotFoundError(V8)
    if not CAT.exists():
        raise FileNotFoundError(CAT)

    df = pd.read_csv(V8)
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
    df["reached_0_5x"] = df["reached_0_5x"].astype(bool)

    cat = pd.read_csv(CAT)
    rows = []

    for _, c in cat.iterrows():
        kind, pairs = parse_candidate(c["candidate_id"])
        g = apply_candidate(df, kind, pairs)
        all_s = stats(g)
        train = g[(g.trade_date >= TRAIN_START) & (g.trade_date <= TRAIN_END)]
        hold = g[(g.trade_date >= HOLD_START) & (g.trade_date <= HOLD_END)]
        tr_s, ho_s = stats(train), stats(hold)

        # Concentration is descriptive, never used to manufacture the rate.
        top_date_share = float(g.trade_date.value_counts(normalize=True).iloc[0]) if not g.empty else None
        top_symbol_share = float(g.symbol.value_counts(normalize=True).iloc[0]) if not g.empty else None

        final_pass = (
            ho_s["n"] >= GATE_N and
            ho_s["rate"] is not None and ho_s["rate"] >= GATE_RATE and
            ho_s["dates"] >= GATE_DATES and
            ho_s["symbols"] >= GATE_SYMBOLS
        )
        rows.append({
            "candidate_id": c["candidate_id"],
            "kind": kind,
            "factors": c.get("factors",""),
            "states": c.get("states",""),
            "all_n": all_s["n"], "all_good_n": all_s["good_n"], "all_bad_n": all_s["bad_n"], "all_rate": all_s["rate"],
            "all_dates": all_s["dates"], "all_symbols": all_s["symbols"],
            "train_n": tr_s["n"], "train_good_n": tr_s["good_n"], "train_bad_n": tr_s["bad_n"], "train_rate": tr_s["rate"],
            "train_dates": tr_s["dates"], "train_symbols": tr_s["symbols"],
            "holdout_n": ho_s["n"], "holdout_good_n": ho_s["good_n"], "holdout_bad_n": ho_s["bad_n"], "holdout_rate": ho_s["rate"],
            "holdout_dates": ho_s["dates"], "holdout_symbols": ho_s["symbols"],
            "top_date_share": top_date_share,
            "top_symbol_share": top_symbol_share,
            "frozen_final_gate_pass": bool(final_pass),
            "status": "FINAL_VALIDATION_CANDIDATE" if final_pass else ("HOLDOUT_RESEARCH" if ho_s["n"] > 0 else "NO_HOLDOUT_SUPPORT")
        })

    r = pd.DataFrame(rows)
    r = r.sort_values(["frozen_final_gate_pass","holdout_rate","holdout_n","all_rate"], ascending=[False,False,False,False])
    r.to_csv(OUT / "chronological_validation.csv", index=False)
    r[r["frozen_final_gate_pass"]].to_csv(OUT / "final_validation_candidates.csv", index=False)
    r[(r["holdout_rate"].fillna(-1) >= 0.67) & (r["holdout_rate"].fillna(-1) < 0.80)].to_csv(OUT / "holdout_research_candidates_67_to_80.csv", index=False)

    summary = {
        "status": "V12_6_CHRONOLOGICAL_VALIDATION_COMPLETE",
        "production_modified": False,
        "train": f"{TRAIN_START} through {TRAIN_END}",
        "holdout": f"{HOLD_START} through {HOLD_END}",
        "frozen_gate": {
            "hit_rate": GATE_RATE,
            "holdout_n": GATE_N,
            "holdout_dates": GATE_DATES,
            "holdout_symbols": GATE_SYMBOLS
        },
        "candidate_count": int(len(r)),
        "final_validation_candidate_count": int(r["frozen_final_gate_pass"].sum()),
        "holdout_research_candidate_count": int(((r["holdout_n"] > 0) & (~r["frozen_final_gate_pass"])).sum()),
        "max_holdout_rate": float(r["holdout_rate"].max()) if r["holdout_rate"].notna().any() else None,
        "note": "This validator preserves the frozen V12.5 gate and chronological split; it does not lower the gate."
    }
    (OUT / "v12_6_validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
