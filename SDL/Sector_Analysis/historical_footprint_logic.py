from __future__ import annotations

"""
NTIS SDL — Historical Reverse-Footprint Logic
FINAL-1.0

Standalone research/freeze utility.
It reads existing SDL historical research data, evaluates simple
direction-aware footprints against a historical outcome, and writes an
auditable freeze file.

It does not modify SDL production logic or raw source files.
"""

from pathlib import Path
import argparse
import json
import math
import re
from datetime import datetime

import numpy as np
import pandas as pd


SDL_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = SDL_ROOT / "data"
OUT_DIR = Path(__file__).resolve().parent / ".sector_intelligence" / "frozen_logic"
OUT_JSON = OUT_DIR / "logic_freeze.json"
OUT_CSV = OUT_DIR / "historical_feature_evidence.csv"

DEFAULT_INPUTS = [
    DATA_ROOT / "output" / "early_prediction_futures_oi_v4_2_controlled"
    / "first_22_point_in_time_controlled.csv",
    DATA_ROOT / "output" / "early_prediction_research"
    / "first_22_point_in_time.csv",
]

MIN_N = 30
MIN_SUCCESS = 8
MIN_LIFT = 1.10

ALIASES = {
    "price": [
        "price_chg_pct", "Price Chg %", "Price Chg%",
        "Price Change %", "Price Change%"
    ],
    "oi": [
        "oi_chg_pct", "OI Chg %", "OI Chg%",
        "oi_chg", "OI Chg", "OI Chg(Value)", "OI Chg (Value)"
    ],
    "ce_oi": [
        "ce_oi_chg", "CE OI Chg", "Call OI Chg", "Tot CE OI Chg"
    ],
    "pe_oi": [
        "pe_oi_chg", "PE OI Chg", "Put OI Chg", "Tot PE OI Chg"
    ],
    "pe_ce": [
        "pe_minus_ce_oi_chg", "PE-CE OI Chg", "Tot PE-CE OI Chg"
    ],
    "volume": [
        "volume_chg_pct", "Volume Chg (%)", "Volume Chg %", "Volume Chg%"
    ],
    "buildup": [
        "futures_buildup", "Futures Buildup", "Future Buildup",
        "Buildup", "Bldp"
    ],
}


def norm(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def resolve(df: pd.DataFrame, names: list[str]) -> str | None:
    lookup = {norm(c): c for c in df.columns}
    for name in names:
        if norm(name) in lookup:
            return lookup[norm(name)]
    return None


def numeric(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(
        series.astype("string")
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def choose_input(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"Specified historical file not found: {path}")
        return path

    for path in DEFAULT_INPUTS:
        if path.exists():
            return path

    # Helpful fallback: search only inside SDL/data/output, never raw source.
    candidates = sorted(
        (DATA_ROOT / "output").glob("**/first_22_point_in_time*.csv")
    )
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "No approved historical research file found under SDL\\data\\output. "
        "Expected first_22_point_in_time_controlled.csv or first_22_point_in_time.csv."
    )


def load_input(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if df.empty:
        raise ValueError(f"Historical file is empty: {path}")
    return df


def detect_direction(df: pd.DataFrame) -> pd.Series:
    for column in ("direction", "Direction", "target_direction"):
        if column not in df.columns:
            continue

        x = df[column].astype("string").str.upper()
        out = pd.Series(pd.NA, index=df.index, dtype="string")
        out.loc[x.str.contains(r"UP|LONG|CALL", regex=True, na=False)] = "UP"
        out.loc[x.str.contains(r"DOWN|SHORT|PUT", regex=True, na=False)] = "DOWN"

        if out.notna().any():
            return out

    price_col = resolve(df, ALIASES["price"])
    if price_col:
        x = numeric(df[price_col])
        return x.map(
            lambda value: "UP" if value > 0
            else "DOWN" if value < 0
            else pd.NA
        ).astype("string")

    return pd.Series(pd.NA, index=df.index, dtype="string")


def direction_support(series: pd.Series, direction: str) -> pd.Series:
    x = numeric(series)
    if direction == "UP":
        return x > 0
    return x < 0


def feature_result(
    df: pd.DataFrame,
    feature: str,
    column: str,
    direction: str,
    target: str,
) -> dict:
    x = numeric(df[column])
    valid = x.notna()

    if not bool(valid.any()):
        return {
            "feature": feature,
            "field": column,
            "direction": direction,
            "target": target,
            "n_valid": 0,
            "support_n": 0,
            "success_n": 0,
            "support_success_n": 0,
            "baseline_rate": None,
            "support_rate": None,
            "lift": None,
            "status": "UNAVAILABLE",
        }

    y = df[target].astype(bool)
    support = direction_support(df[column], direction)
    mask = valid

    yy = y.loc[mask]
    ss = support.loc[mask]

    baseline = float(yy.mean()) if len(yy) else math.nan
    support_n = int(ss.sum())
    support_success = int((ss & yy).sum())
    support_rate = support_success / support_n if support_n else math.nan
    lift = support_rate / baseline if baseline > 0 else math.nan

    status = "RESEARCH_ONLY"
    if (
        len(yy) >= MIN_N
        and support_n >= MIN_SUCCESS
        and math.isfinite(lift)
        and lift >= MIN_LIFT
    ):
        status = "FREEZE_CANDIDATE"

    return {
        "feature": feature,
        "field": column,
        "direction": direction,
        "target": target,
        "n_valid": int(len(yy)),
        "support_n": support_n,
        "success_n": int(yy.sum()),
        "support_success_n": support_success,
        "baseline_rate": None if not math.isfinite(baseline) else baseline,
        "support_rate": None if not math.isfinite(support_rate) else support_rate,
        "lift": None if not math.isfinite(lift) else lift,
        "status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an auditable historical footprint logic freeze."
    )
    parser.add_argument("--input", help="Approved historical CSV")
    parser.add_argument(
        "--target",
        default="target_50_reached",
        help="Historical outcome column (default: target_50_reached)",
    )
    args = parser.parse_args()

    path = choose_input(args.input)
    df = load_input(path)

    if args.target not in df.columns:
        raise ValueError(
            f"Outcome column '{args.target}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    target = df[args.target].astype(bool)
    direction = detect_direction(df)

    work = df.copy()
    work["_direction"] = direction

    results: list[dict] = []

    for feature, aliases in ALIASES.items():
        column = resolve(work, aliases)

        if column is None:
            results.append({
                "feature": feature,
                "field": None,
                "direction": None,
                "target": args.target,
                "n_valid": 0,
                "support_n": 0,
                "success_n": int(target.sum()),
                "support_success_n": 0,
                "baseline_rate": float(target.mean()),
                "support_rate": None,
                "lift": None,
                "status": "UNAVAILABLE",
            })
            continue

        produced = False

        for direction_name in ("UP", "DOWN"):
            mask = work["_direction"].eq(direction_name)
            if int(mask.sum()) >= MIN_N:
                results.append(
                    feature_result(
                        work.loc[mask],
                        feature,
                        column,
                        direction_name,
                        args.target,
                    )
                )
                produced = True

        if not produced:
            results.append({
                "feature": feature,
                "field": column,
                "direction": None,
                "target": args.target,
                "n_valid": int(numeric(work[column]).notna().sum()),
                "support_n": 0,
                "success_n": int(target.sum()),
                "support_success_n": 0,
                "baseline_rate": float(target.mean()),
                "support_rate": None,
                "lift": None,
                "status": "DIRECTION_UNAVAILABLE",
            })

    result_df = pd.DataFrame(results)
    frozen = result_df[
        result_df["status"].eq("FREEZE_CANDIDATE")
    ].to_dict("records")

    freeze = {
        "logic_version": "FINAL-1.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "method": "historical reverse-footprint evidence",
        "input": str(path),
        "events": int(len(work)),
        "outcome": args.target,
        "minimum_observations": MIN_N,
        "minimum_successes": MIN_SUCCESS,
        "minimum_lift": MIN_LIFT,
        "frozen_features": frozen,
        "rules": [
            "Use only information available at the observation boundary.",
            "Missing evidence is UNAVAILABLE, never zero.",
            "Do not create a composite score from unvalidated weights.",
            "Do not display a probability unless separately validated.",
            "A frozen feature is evidence support, not a trade guarantee.",
            "SDL stock qualification remains the final stock-level gate.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUT_CSV, index=False)
    OUT_JSON.write_text(
        json.dumps(freeze, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"INPUT: {path}")
    print(f"EVENTS: {len(work)}")
    print(f"OUTCOME: {args.target}")
    print(f"BASELINE: {target.mean():.4f}")
    print(f"FROZEN FEATURE CANDIDATES: {len(frozen)}")

    for row in frozen:
        print(
            f"  {row['feature']} [{row['direction']}] "
            f"n={row['n_valid']} support={row['support_n']} "
            f"lift={row['lift']:.3f}"
        )

    print(f"FREEZE FILE: {OUT_JSON}")
    print(f"AUDIT FILE: {OUT_CSV}")


if __name__ == "__main__":
    main()
