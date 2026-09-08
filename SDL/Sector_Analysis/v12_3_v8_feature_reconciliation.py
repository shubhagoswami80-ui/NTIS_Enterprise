from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

BASE = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\.sector_intelligence")
OUT = BASE / "v12_3_v8_feature_reconciliation"
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATE = BASE / "maturity_conditional_pattern_discovery_v8" / "conditional_pattern_candidates.csv"
OUTCOME = BASE / "smart_replay_hit_discovery" / "multi_window_outcomes.csv"


def norm(x):
    return re.sub(r"[^a-z0-9]+", "_", str(x).strip().lower()).strip("_")


def split_terms(expr):
    return [x.strip() for x in re.split(r"\s*&\s*", str(expr)) if x.strip()]


def derive_features(d):
    x = d.copy()

    # Reconstruct only features that can be deterministically derived from
    # fields present in multi_window_outcomes.csv.
    x["price_dir"] = x["orb_direction"].astype(str).str.upper()
    x["price_state"] = x["price_dir"].map({"UP": "POS", "DOWN": "NEG"})

    # The replay source contains direction_agree, which is the authoritative
    # available agreement field for the V8-era ORB agreement feature.
    if "direction_agree" in x.columns:
        agree = x["direction_agree"].astype(str).str.upper()
        x["orb_agree"] = agree.map({
            "TRUE": "YES", "1": "YES", "YES": "YES",
            "FALSE": "NO", "0": "NO", "NO": "NO",
        }).fillna(agree)
        x["orb_price_agree"] = x["orb_agree"]
    else:
        x["orb_agree"] = "UNKNOWN"
        x["orb_price_agree"] = "UNKNOWN"

    magnitude_cols = [
        "fut_gt500", "fut_gt1000", "fut_lt500", "fut_lt1000",
        "ce_gt500", "ce_gt1000", "ce_lt500", "ce_lt1000",
        "pe_gt500", "pe_gt1000", "pe_lt500", "pe_lt1000",
        "pec_gt500", "pec_gt1000", "pec_lt500", "pec_lt1000",
    ]
    present = [c for c in magnitude_cols if c in x.columns]
    x["magnitude_count"] = (
        x[present].fillna(False).astype(bool).sum(axis=1) if present
        else 0
    )
    x["magnitude_count_band"] = pd.cut(
        x["magnitude_count"],
        bins=[-1, 0, 1, float("inf")],
        labels=["0", "1", "2+"],
    ).astype(str)

    if "volume_pct" in x.columns:
        vp = pd.to_numeric(x["volume_pct"], errors="coerce")
        x["volume_state"] = vp.map(
            lambda v: "POS" if pd.notna(v) and v > 0
            else "NEG" if pd.notna(v) and v < 0
            else "FLAT"
        )
    else:
        x["volume_state"] = "UNKNOWN"

    return x


def apply_expression(df, expr):
    mask = pd.Series(True, index=df.index)
    cols = {norm(c): c for c in df.columns}

    for term in split_terms(expr):
        m = re.match(r"^(.+?)\s*=\s*(.+)$", term)
        if not m:
            return None, f"unsupported_term:{term}"

        field = norm(m.group(1))
        expected = norm(m.group(2))

        col = cols.get(field)
        if col is None:
            return None, f"unmapped_feature:{field}"

        vals = df[col].astype(str).map(norm)
        mask &= vals.eq(expected)

    return mask, "OK"


def as_set(value):
    if pd.isna(value):
        return set()
    return {x.strip() for x in re.split(r"[,;| ]+", str(value)) if x.strip()}


def main():
    if not CANDIDATE.exists():
        raise FileNotFoundError(CANDIDATE)
    if not OUTCOME.exists():
        raise FileNotFoundError(OUTCOME)

    cand = pd.read_csv(CANDIDATE, low_memory=False)
    out = pd.read_csv(OUTCOME, low_memory=False)

    required_c = {"orb_minutes", "maturity", "pattern_features", "n",
                  "dates", "symbols", "hit_rate"}
    required_o = {"orb_minutes", "symbol", "trade_date", "reached_0.5x"}
    mc = required_c - set(cand.columns)
    mo = required_o - set(out.columns)
    if mc or mo:
        raise RuntimeError(f"Candidate missing={sorted(mc)} outcome missing={sorted(mo)}")

    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.date
    out = out.dropna(subset=["trade_date"]).copy()
    out = derive_features(out)

    # Reconcile every V8 candidate, not only the 60-<67% subset.
    records = []
    for _, c in cand.iterrows():
        minutes = int(c["orb_minutes"])
        expr = str(c["pattern_features"])

        pool = out[out["orb_minutes"].astype(int).eq(minutes)]
        mask, reason = apply_expression(pool, expr)

        rec = {
            "orb_minutes": minutes,
            "maturity": c["maturity"],
            "pattern_features": expr,
            "v8_n": int(c["n"]),
            "v8_dates": c["dates"],
            "v8_symbols": c["symbols"],
            "v8_hit_rate": float(c["hit_rate"]),
            "matched": False,
            "reason": reason,
            "reconstructed_n": 0,
            "reconstructed_dates": 0,
            "reconstructed_symbols": 0,
            "reconstructed_hit_rate": None,
            "n_match": False,
            "dates_match": False,
            "symbols_match": False,
            "hit_rate_match": False,
            "population_match": False,
        }

        if mask is not None:
            m = pool.loc[mask, ["symbol", "trade_date", "reached_0.5x"]].copy()
            target = m["reached_0.5x"].astype(str).str.upper().isin(
                ["TRUE", "1", "YES"]
            )
            rec["matched"] = True
            rec["reason"] = "OK"
            rec["reconstructed_n"] = int(len(m))
            rec["reconstructed_dates"] = int(m["trade_date"].nunique())
            rec["reconstructed_symbols"] = int(m["symbol"].nunique())
            rec["reconstructed_hit_rate"] = float(target.mean()) if len(m) else None
            rec["n_match"] = rec["reconstructed_n"] == rec["v8_n"]

            # V8's dates/symbols fields may be counts rather than lists.
            def numeric_or_none(v):
                try:
                    return int(float(v))
                except Exception:
                    return None

            vd = numeric_or_none(c["dates"])
            vs = numeric_or_none(c["symbols"])
            if vd is not None:
                rec["dates_match"] = rec["reconstructed_dates"] == vd
            if vs is not None:
                rec["symbols_match"] = rec["reconstructed_symbols"] == vs

            rec["hit_rate_match"] = (
                rec["reconstructed_hit_rate"] is not None
                and abs(rec["reconstructed_hit_rate"] - rec["v8_hit_rate"]) < 1e-9
            )
            rec["population_match"] = (
                rec["n_match"]
                and (rec["dates_match"] if vd is not None else True)
                and (rec["symbols_match"] if vs is not None else True)
                and rec["hit_rate_match"]
            )

        records.append(rec)

    result = pd.DataFrame(records)
    result.to_csv(OUT / "v12_3_v8_candidate_reconciliation.csv", index=False)

    matched = result[result["matched"]]
    pop = result[result["population_match"]]
    summary = {
        "status": "READY",
        "study": "V12_3_V8_FEATURE_RECONCILIATION",
        "v8_candidate_rows": int(len(cand)),
        "feature_expression_resolved": int(len(matched)),
        "feature_expression_unmapped": int((~result["matched"]).sum()),
        "population_exact_matches": int(len(pop)),
        "population_match_rate": float(len(pop) / len(result)) if len(result) else 0.0,
        "max_reconstructed_hit_rate": (
            float(pd.to_numeric(matched["reconstructed_hit_rate"], errors="coerce").max())
            if len(matched) else None
        ),
        "authoritative_target": "existing reached_0.5x",
        "fixed_0.5_percent_target_used": False,
        "production_changes": False,
        "next_gate": (
            "Only exact population matches may proceed to independent holdout."
        ),
    }
    (OUT / "v12_3_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"OUTPUT_DIR: {OUT}")


if __name__ == "__main__":
    main()
