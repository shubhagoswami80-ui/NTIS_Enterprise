from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


TARGET = "reached_0_5x"
PATTERN = {
    "orb_minutes": 10,
    "maturity": "09:45",
    "price_dir": "DOWN",
    "orb_agree": "NO",
    "magnitude_count_band": "0",
}

# Frozen acceptance gate. Do not lower.
HARD_GATE = 0.80
MIN_OUTCOMES = 30
MIN_DATES = 3
MIN_SYMBOLS = 10


def norm_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "up", "down"}


def find_first(root: Path, names: Iterable[str]) -> Path | None:
    wanted = {n.lower() for n in names}
    for p in root.rglob("*"):
        if p.is_file() and p.name.lower() in wanted:
            return p
    return None


def read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def prepare_matrix(path: Path) -> pd.DataFrame:
    df = read_csv(path)
    required = {
        "orb_minutes",
        "symbol",
        "trade_date",
        "maturity",
        TARGET,
        "price_dir",
        "orb_agree",
        "magnitude_count_band",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Exact V8 matrix is missing required columns: {missing}")

    df["orb_minutes"] = pd.to_numeric(df["orb_minutes"], errors="coerce")
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df[TARGET] = df[TARGET].map(norm_bool)

    for c in ["maturity", "price_dir", "orb_agree", "magnitude_count_band"]:
        df[c] = df[c].astype(str).str.strip().str.upper()

    return df


def select_pattern(df: pd.DataFrame) -> pd.DataFrame:
    mask = (
        df["orb_minutes"].eq(PATTERN["orb_minutes"])
        & df["maturity"].eq(PATTERN["maturity"].upper())
        & df["price_dir"].eq(PATTERN["price_dir"])
        & df["orb_agree"].eq(PATTERN["orb_agree"])
        & df["magnitude_count_band"].eq(PATTERN["magnitude_count_band"])
    )
    return df.loc[mask].copy()


def summarize(group: pd.DataFrame) -> dict:
    if group.empty:
        return {
            "n": 0,
            "good_n": 0,
            "good_rate": None,
            "bad_n": 0,
            "bad_rate": None,
            "dates": 0,
            "symbols": 0,
        }

    good = int(group[TARGET].sum())
    n = len(group)
    return {
        "n": n,
        "good_n": good,
        "good_rate": good / n,
        "bad_n": n - good,
        "bad_rate": (n - good) / n,
        "dates": int(group["trade_date"].nunique()),
        "symbols": int(group["symbol"].nunique()),
    }


def feature_comparison(group: pd.DataFrame) -> pd.DataFrame:
    excluded = {
        "orb_minutes", "symbol", "trade_date", "maturity", TARGET,
        "price_dir", "orb_agree", "magnitude_count_band"
    }
    features = [c for c in group.columns if c not in excluded]

    rows = []
    good = group[group[TARGET]]
    bad = group[~group[TARGET]]

    for c in features:
        if group[c].nunique(dropna=True) > 20:
            continue

        for state in sorted(group[c].dropna().astype(str).unique()):
            all_n = int(group[c].astype(str).eq(state).sum())
            good_n = int(good[c].astype(str).eq(state).sum())
            bad_n = int(bad[c].astype(str).eq(state).sum())
            if all_n == 0:
                continue
            rows.append({
                "feature": c,
                "state": state,
                "n": all_n,
                "good_n": good_n,
                "good_rate": good_n / all_n,
                "bad_n": bad_n,
                "bad_rate": bad_n / all_n,
                "good_share_of_good": good_n / len(good) if len(good) else None,
                "bad_share_of_bad": bad_n / len(bad) if len(bad) else None,
            })

    return pd.DataFrame(rows).sort_values(
        ["good_rate", "n"], ascending=[False, False]
    ) if rows else pd.DataFrame()


def chronological_split(group: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(group["trade_date"].dropna().unique())
    if len(dates) < 2:
        return group.copy(), group.iloc[0:0].copy()

    # Diagnostic split only. This does not replace the historical V12.5 split.
    holdout_n = max(1, len(dates) // 3)
    holdout_dates = set(dates[-holdout_n:])
    train = group[~group["trade_date"].isin(holdout_dates)].copy()
    hold = group[group["trade_date"].isin(holdout_dates)].copy()
    return train, hold


def path_trace(pattern: pd.DataFrame, canonical_path: Path | None) -> pd.DataFrame:
    """
    Optional path trace.

    The exact V8 matrix is authoritative for feature/outcome membership.
    Canonical observations are used only to describe the price path after
    the selected maturity. They never alter the target or qualification.
    """
    if canonical_path is None or pattern.empty:
        return pd.DataFrame()

    c = read_csv(canonical_path)
    required = {"symbol", "timestamp", "price_chg"}
    if not required.issubset(c.columns):
        return pd.DataFrame()

    c["symbol"] = c["symbol"].astype(str).str.strip()
    c["timestamp"] = pd.to_datetime(c["timestamp"], errors="coerce")
    c["price_chg"] = pd.to_numeric(c["price_chg"], errors="coerce")
    c = c.dropna(subset=["symbol", "timestamp"]).sort_values(
        ["symbol", "timestamp"]
    )

    rows = []
    for _, r in pattern.iterrows():
        date = r["trade_date"]
        sym = r["symbol"]
        maturity_time = pd.Timestamp(f"{date} {r['maturity']}")
        g = c[
            c["symbol"].eq(sym)
            & c["timestamp"].dt.date.eq(date)
            & c["timestamp"].ge(maturity_time)
        ].copy()

        if g.empty:
            rows.append({
                "symbol": sym,
                "trade_date": str(date),
                "maturity": r["maturity"],
                TARGET: bool(r[TARGET]),
                "later_observations": 0,
                "first_later_timestamp": None,
                "last_later_timestamp": None,
                "path_price_chg_sum": None,
                "path_price_chg_min": None,
                "path_price_chg_max": None,
            })
            continue

        rows.append({
            "symbol": sym,
            "trade_date": str(date),
            "maturity": r["maturity"],
            TARGET: bool(r[TARGET]),
            "later_observations": len(g),
            "first_later_timestamp": str(g["timestamp"].min()),
            "last_later_timestamp": str(g["timestamp"].max()),
            "path_price_chg_sum": float(g["price_chg"].sum()),
            "path_price_chg_min": float(g["price_chg"].min()),
            "path_price_chg_max": float(g["price_chg"].max()),
        })

    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="V12.6 Phase 2 reverse trace. Research only; no production/dashboard changes."
    )
    ap.add_argument(
        "--root",
        required=True,
        help="SDL/Sector_Analysis root containing .sector_intelligence",
    )
    ap.add_argument(
        "--matrix",
        default="",
        help="Optional exact V8 maturity_feature_matrix.csv path",
    )
    ap.add_argument(
        "--canonical",
        default="",
        help="Optional canonical_strength_observations.csv for post-maturity path diagnostics",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    matrix = Path(args.matrix) if args.matrix else find_first(
        root, ["maturity_feature_matrix.csv"]
    )
    if matrix is None or not matrix.is_file():
        raise SystemExit(
            "EXACT_V8_MATRIX_NOT_FOUND: supply --matrix pointing to the preserved "
            "maturity_feature_matrix.csv"
        )

    canonical = (
        Path(args.canonical)
        if args.canonical
        else find_first(root, ["canonical_strength_observations.csv"])
    )

    df = prepare_matrix(matrix)
    pattern = select_pattern(df)

    overall = summarize(pattern)
    train, hold = chronological_split(pattern)

    summary = {
        "status": "V12_6_PHASE2_REVERSE_TRACE_COMPLETE",
        "production_modified": False,
        "exact_v8_matrix": str(matrix),
        "canonical_path_used": str(canonical) if canonical else None,
        "authoritative_target": TARGET,
        "target_semantics": "50% of opening straddle value",
        "pattern": PATTERN,
        "pattern_overall": overall,
        "diagnostic_train": summarize(train),
        "diagnostic_holdout": summarize(hold),
        "frozen_validation_gate": {
            "hit_rate": HARD_GATE,
            "minimum_outcomes": MIN_OUTCOMES,
            "minimum_dates": MIN_DATES,
            "minimum_symbols": MIN_SYMBOLS,
        },
        "validation_status": (
            "NOT_VALIDATED"
            if (
                overall["n"] < MIN_OUTCOMES
                or overall["dates"] < MIN_DATES
                or overall["symbols"] < MIN_SYMBOLS
                or (overall["good_rate"] or 0) < HARD_GATE
            )
            else "MEETS_RESEARCH_GATE_ONLY"
        ),
        "notes": [
            "Exact V8 matrix is consumed directly; V8 semantics are not reconstructed.",
            "The pattern is a research lead, not a production rule.",
            "Chronological train/holdout split here is diagnostic only and does not replace V12.5's frozen historical split.",
            "Canonical path observations are descriptive only and cannot alter target membership.",
            "Missing data is not treated as zero or failure.",
            "No dashboard, qualification, ranking, gate, or production logic is modified.",
        ],
    }

    pattern.to_csv(out / "pattern_population.csv", index=False)
    feature_comparison(pattern).to_csv(
        out / "winner_failure_feature_comparison.csv", index=False
    )

    if not train.empty or not hold.empty:
        pd.DataFrame([
            {"split": "ALL", **summarize(pattern)},
            {"split": "DIAGNOSTIC_TRAIN", **summarize(train)},
            {"split": "DIAGNOSTIC_HOLDOUT", **summarize(hold)},
        ]).to_csv(out / "chronological_summary.csv", index=False)

    trace = path_trace(pattern, canonical)
    if not trace.empty:
        trace.to_csv(out / "post_maturity_path_trace.csv", index=False)

    (out / "v12_6_phase2_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
