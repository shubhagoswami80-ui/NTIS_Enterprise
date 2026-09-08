from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


BASE = Path(r"E:\NSE_Daily_Analysis\SDL\Sector_Analysis\.sector_intelligence")
OUT = BASE / "v12_independent_event_holdout"

OUT.mkdir(parents=True, exist_ok=True)

OUTCOME = BASE / "smart_replay_hit_discovery" / "multi_window_outcomes.csv"
CANDIDATE_FILES = [
    BASE / "maturity_conditional_pattern_discovery" / "candidate_patterns.csv",
    BASE / "maturity_conditional_pattern_discovery_v8" / "candidate_patterns.csv",
    BASE / "maturity_conditional_pattern_discovery_v8" / "v8_candidates.csv",
    BASE / "maturity_conditional_pattern_discovery" / "v8_candidates.csv",
    BASE / "near_hit_forensics" / "near_hit_candidates.csv",
]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def find_candidate_file() -> Path | None:
    # Prefer V8-era candidate files, then any candidate CSV under the study root.
    for p in CANDIDATE_FILES:
        if p.exists():
            return p
    hits = []
    for p in BASE.rglob("*.csv"):
        n = norm(p.name)
        if "candidate" in n and "pattern" in n:
            hits.append(p)
        elif "v8" in n and "candidate" in n:
            hits.append(p)
    return sorted(hits, key=lambda x: (len(x.parts), str(x)))[0] if hits else None


def find_pattern_column(df: pd.DataFrame) -> str | None:
    # V8 candidate schema uses `pattern_features` for the rule expression.
    # Keep compatibility with earlier candidate schemas as well.
    for c in [
        "pattern_features",
        "pattern",
        "pattern_expression",
        "conditions",
        "condition",
        "rule",
    ]:
        if c in df.columns:
            return c
    return None


def find_rate_column(df: pd.DataFrame) -> str | None:
    for c in ["favorable_rate", "hit_rate", "rate", "reached_0.5x_rate",
              "reached_0_5x_rate", "favorable_pct"]:
        if c in df.columns:
            return c
    return None


def split_terms(expr: str) -> list[str]:
    # V8 pattern_features are conjunctions. Accept &, AND, and comma separators.
    return [
        x.strip()
        for x in re.split(r"\s*&\s*|\s+AND\s+|\s*,\s*", str(expr), flags=re.I)
        if x.strip()
    ]


def bool_mask(df: pd.DataFrame, terms: list[str]) -> pd.Series | None:
    mask = pd.Series(True, index=df.index)
    candidates = {norm(c): c for c in df.columns}

    for raw_term in terms:
        term = raw_term.strip()
        m = re.match(r"^(.+?)\s*(?:=|:)\s*(.+)$", term)
        if m:
            field = norm(m.group(1))
            expected = m.group(2).strip().strip("'\"").upper()
            col = candidates.get(field)
            if col is None:
                return None

            s = df[col]
            vals = s.astype(str).str.strip().str.upper()

            if expected in {"TRUE", "YES", "Y", "1"}:
                mask &= vals.isin(["TRUE", "YES", "Y", "1", "UP"])
            elif expected in {"FALSE", "NO", "N", "0"}:
                mask &= vals.isin(["FALSE", "NO", "N", "0", "DOWN"])
            else:
                # Exact categorical comparison. Numeric-looking values are
                # also handled without forcing them to booleans.
                mask &= vals.eq(expected)
            continue

        # Bare boolean feature, e.g. orb_up.
        field = norm(term)
        col = candidates.get(field)
        if col is None:
            return None
        vals = df[col].astype(str).str.strip().str.upper()
        if vals.isin(["TRUE", "FALSE"]).any():
            mask &= vals.eq("TRUE")
        else:
            mask &= df[col].fillna(False).astype(bool)

    return mask


def main() -> None:
    if not OUTCOME.exists():
        raise FileNotFoundError(f"Outcome file not found: {OUTCOME}")

    cand_path = find_candidate_file()
    if cand_path is None:
        raise FileNotFoundError("No V8 candidate CSV could be located.")

    outcomes = pd.read_csv(OUTCOME, low_memory=False)
    candidates = pd.read_csv(cand_path, low_memory=False)

    pattern_col = find_pattern_column(candidates)
    rate_col = find_rate_column(candidates)
    if not pattern_col or not rate_col:
        raise RuntimeError(
            f"Candidate schema unsupported. pattern_col={pattern_col!r}, "
            f"rate_col={rate_col!r}, columns={list(candidates.columns)}"
        )

    # Independent holdout is by trading date, never by individual rows.
    # This prevents events from the same date leaking across train/test.
    if "trade_date" not in outcomes.columns:
        raise RuntimeError("Outcome data has no trade_date column.")
    outcomes["trade_date"] = pd.to_datetime(
        outcomes["trade_date"], errors="coerce"
    ).dt.date
    outcomes = outcomes.dropna(subset=["trade_date"]).copy()

    target_col = next(
        (c for c in ["reached_0.5x", "reached_0_5x"] if c in outcomes.columns),
        None,
    )
    if target_col is None:
        raise RuntimeError("Authoritative reached_0.5x field is missing.")

    # Only V8 near-hit research candidates: 67% is the lower research gate,
    # but candidates below 67% are retained only for audit comparison.
    rate = pd.to_numeric(candidates[rate_col], errors="coerce")
    candidates = candidates.assign(_rate=rate)
    candidates = candidates[candidates["_rate"].between(0.60, 0.80, inclusive="left")].copy()

    dates = sorted(outcomes["trade_date"].unique())
    if len(dates) < 6:
        raise RuntimeError(f"Too few dates for an independent holdout: {len(dates)}")

    # Chronological date holdout: earliest 70% train, latest 30% holdout.
    cut = max(1, min(len(dates) - 1, int(len(dates) * 0.70)))
    train_dates = set(dates[:cut])
    holdout_dates = set(dates[cut:])

    rows = []
    for _, cand in candidates.iterrows():
        expr = str(cand[pattern_col])
        terms = split_terms(expr)
        mask = bool_mask(outcomes, terms)
        if mask is None:
            rows.append({
                "pattern": expr,
                "research_rate": float(cand["_rate"]),
                "train_n": 0,
                "train_rate": None,
                "holdout_n": 0,
                "holdout_rate": None,
                "holdout_dates": 0,
                "classification": "UNRESOLVED",
            })
            continue

        matched = outcomes.loc[mask, ["trade_date", target_col]].copy()
        matched["target"] = matched[target_col].astype(str).str.upper().isin(
            ["TRUE", "1", "YES"]
        )

        tr = matched[matched["trade_date"].isin(train_dates)]
        ho = matched[matched["trade_date"].isin(holdout_dates)]

        tr_rate = float(tr["target"].mean()) if len(tr) else None
        ho_rate = float(ho["target"].mean()) if len(ho) else None

        # Final validation remains >=80%; 67-<80 is research only.
        if ho_rate is not None and ho_rate >= 0.80 and len(ho) >= 30:
            cls = "FINAL_VALIDATION_CANDIDATE"
        elif ho_rate is not None and ho_rate >= 0.67:
            cls = "OPTIMIZATION_RESEARCH"
        elif ho_rate is not None:
            cls = "NOT_VALIDATED"
        else:
            cls = "NO_HOLDOUT_EVENTS"

        rows.append({
            "pattern": expr,
            "research_rate": float(cand["_rate"]),
            "train_n": int(len(tr)),
            "train_rate": tr_rate,
            "holdout_n": int(len(ho)),
            "holdout_rate": ho_rate,
            "holdout_dates": int(ho["trade_date"].nunique()),
            "classification": cls,
        })

    result = pd.DataFrame(rows)
    result.to_csv(OUT / "v12_holdout_by_candidate.csv", index=False)

    valid = result[result["classification"] != "UNRESOLVED"].copy()
    summary = {
        "status": "READY",
        "study": "V12_INDEPENDENT_EVENT_LEVEL_HOLDOUT",
        "candidate_file": str(cand_path),
        "candidate_rows_tested": int(len(candidates)),
        "candidate_rows_resolved": int(len(valid)),
        "total_dates": int(len(dates)),
        "train_dates": int(len(train_dates)),
        "holdout_dates": int(len(holdout_dates)),
        "train_date_start": str(min(train_dates)),
        "train_date_end": str(max(train_dates)),
        "holdout_date_start": str(min(holdout_dates)),
        "holdout_date_end": str(max(holdout_dates)),
        "final_validation_candidates": int(
            (result["classification"] == "FINAL_VALIDATION_CANDIDATE").sum()
        ),
        "optimization_research_candidates": int(
            (result["classification"] == "OPTIMIZATION_RESEARCH").sum()
        ),
        "not_validated_candidates": int(
            (result["classification"] == "NOT_VALIDATED").sum()
        ),
        "authoritative_target": target_col,
        "fixed_0.5_percent_target_used": False,
        "same_date_train_holdout_leakage": False,
        "production_changes": False,
    }
    final_rates = pd.to_numeric(result["holdout_rate"], errors="coerce").dropna()
    summary["max_holdout_rate"] = float(final_rates.max()) if len(final_rates) else None
    result.sort_values(
        ["holdout_rate", "holdout_n"], ascending=[False, False], inplace=False
    ).head(25).to_csv(OUT / "v12_top_holdout_candidates.csv", index=False)

    (OUT / "v12_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))
    print(f"OUTPUT_DIR: {OUT}")


if __name__ == "__main__":
    main()
