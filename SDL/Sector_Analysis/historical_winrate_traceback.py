from __future__ import annotations

"""
NTIS SDL — Historical Win-Rate Traceback
FINAL-1.1

Goal:
Find simple pre-outcome footprint combinations that historically achieve
>= 80% win rate, without look-ahead leakage.

Important:
- This is a research/freeze utility, not a trade executor.
- It uses the existing SDL historical first-point-in-time dataset.
- It tests combinations of observable directional footprints.
- A footprint must be present BEFORE the recorded outcome.
- No missing value is treated as support.
- Patterns with insufficient sample size are not frozen.

Default minimum sample is 20 observations.  This avoids freezing a pattern
from only a handful of examples.  The threshold can be raised later if
the dataset grows.
"""

from pathlib import Path
import argparse
import itertools
import json
import math
from datetime import datetime

import numpy as np
import pandas as pd


SDL_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = SDL_ROOT / "data"

DEFAULT_INPUTS = [
    DATA_ROOT / "output" / "early_prediction_futures_oi_v4_2_controlled"
    / "first_22_point_in_time_controlled.csv",
    DATA_ROOT / "output" / "early_prediction_research"
    / "first_22_point_in_time.csv",
]

OUT_DIR = (
    Path(__file__).resolve().parent
    / ".sector_intelligence"
    / "winrate_traceback"
)
OUT_PATTERNS = OUT_DIR / "validated_patterns.csv"
OUT_FEATURES = OUT_DIR / "feature_direction_audit.csv"
OUT_JSON = OUT_DIR / "winrate_freeze.json"

MIN_SAMPLE = 20
MIN_WIN_RATE = 0.80
MAX_COMBINATION_SIZE = 3

ALIASES = {
    "price": [
        "price_chg_pct", "Price Chg %", "Price Chg%", "Price Change %"
    ],
    "oi": [
        "oi_chg_pct", "OI Chg %", "OI Chg%",
        "oi_chg", "OI Chg", "OI Chg(Value)"
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
    import re
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def resolve(df: pd.DataFrame, names: list[str]) -> str | None:
    lookup = {norm(c): c for c in df.columns}
    for name in names:
        hit = lookup.get(norm(name))
        if hit:
            return hit
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
        p = Path(explicit)
        if not p.exists():
            raise FileNotFoundError(f"Historical file not found: {p}")
        return p

    for p in DEFAULT_INPUTS:
        if p.exists():
            return p

    candidates = sorted(
        (DATA_ROOT / "output").glob("**/first_22_point_in_time*.csv")
    )
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "No approved first-point-in-time historical CSV found under "
        "SDL\\data\\output."
    )


def find_target(df: pd.DataFrame, requested: str) -> str:
    if requested in df.columns:
        return requested

    # Existing research may use a slightly different target name.
    aliases = {
        "target_50_reached": [
            "target_50_reached", "reached_50", "reached50",
            "target50", "target_50"
        ]
    }
    for name in aliases.get(requested, []):
        if name in df.columns:
            return name

    raise ValueError(
        f"Outcome column '{requested}' not found. "
        f"Available columns: {list(df.columns)}"
    )


def detect_direction(df: pd.DataFrame, price_col: str | None) -> pd.Series:
    for c in ("direction", "Direction", "target_direction"):
        if c not in df.columns:
            continue

        x = df[c].astype("string").str.upper()
        out = pd.Series(pd.NA, index=df.index, dtype="string")
        out.loc[x.str.contains(r"UP|LONG|CALL", regex=True, na=False)] = "UP"
        out.loc[
            x.str.contains(r"DOWN|SHORT|PUT", regex=True, na=False)
        ] = "DOWN"

        if out.notna().any():
            return out

    if price_col:
        x = numeric(df[price_col])
        return x.map(
            lambda v: "UP" if v > 0
            else "DOWN" if v < 0
            else pd.NA
        ).astype("string")

    return pd.Series(pd.NA, index=df.index, dtype="string")


def make_feature_matrix(
    df: pd.DataFrame,
    direction: pd.Series,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Each feature is direction-normalized:
      1 = footprint supports the eventual direction
      0 = footprint does not support it
      NaN = unavailable.

    This makes combinations comparable between UP and DOWN events.
    """
    matrix = pd.DataFrame(index=df.index)
    fields = []

    for feature, aliases in ALIASES.items():
        col = resolve(df, aliases)
        if not col:
            continue

        x = numeric(df[col])
        up = x > 0
        down = x < 0

        normalized = pd.Series(np.nan, index=df.index, dtype="float64")
        normalized.loc[direction.eq("UP") & up] = 1.0
        normalized.loc[direction.eq("DOWN") & down] = 1.0
        normalized.loc[
            direction.eq("UP") & down
        ] = 0.0
        normalized.loc[
            direction.eq("DOWN") & up
        ] = 0.0

        matrix[feature] = normalized
        fields.append(feature)

    return matrix, fields


def evaluate_combination(
    matrix: pd.DataFrame,
    outcome: pd.Series,
    direction: pd.Series,
    features: tuple[str, ...],
) -> dict:
    """
    Complete-case test.

    A pattern occurrence exists only when every footprint in the pattern is
    available and supports the event direction.

    This is deliberately conservative: no imputation and no partial credit.
    """
    complete = matrix.loc[:, list(features)].notna().all(axis=1)
    support = matrix.loc[:, list(features)].eq(1).all(axis=1)
    occurrence = complete & support & direction.notna()

    n = int(occurrence.sum())
    if n == 0:
        return {
            "pattern": " + ".join(features),
            "features": "|".join(features),
            "n": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "status": "NO_OCCURRENCES",
        }

    y = outcome.loc[occurrence].astype(bool)
    wins = int(y.sum())
    losses = int(n - wins)
    rate = wins / n

    status = (
        "VALIDATED_80_PLUS"
        if n >= MIN_SAMPLE and rate >= MIN_WIN_RATE
        else "RESEARCH_ONLY"
    )

    return {
        "pattern": " + ".join(features),
        "features": "|".join(features),
        "n": n,
        "wins": wins,
        "losses": losses,
        "win_rate": rate,
        "status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Approved historical CSV")
    parser.add_argument("--target", default="target_50_reached")
    parser.add_argument("--min-sample", type=int, default=MIN_SAMPLE)
    parser.add_argument("--min-win-rate", type=float, default=MIN_WIN_RATE)
    args = parser.parse_args()

    path = choose_input(args.input)
    df = pd.read_csv(path, low_memory=False)

    if df.empty:
        raise ValueError(f"Historical file is empty: {path}")

    target_col = find_target(df, args.target)
    outcome = df[target_col].astype(bool)

    price_col = resolve(df, ALIASES["price"])
    direction = detect_direction(df, price_col)

    matrix, fields = make_feature_matrix(df, direction)

    if not fields:
        raise ValueError(
            "No approved footprint fields could be resolved from the file."
        )

    feature_rows = []
    for feature in fields:
        available = matrix[feature].notna()
        support = matrix[feature].eq(1)
        n = int(available.sum())
        support_n = int(support.sum())
        wins = int(outcome.loc[support].sum()) if support_n else 0
        rate = wins / support_n if support_n else math.nan

        feature_rows.append({
            "feature": feature,
            "n_available": n,
            "support_n": support_n,
            "wins_when_supporting": wins,
            "win_rate_when_supporting": (
                None if not math.isfinite(rate) else rate
            ),
        })

    patterns = []
    for size in range(1, min(MAX_COMBINATION_SIZE, len(fields)) + 1):
        for combo in itertools.combinations(fields, size):
            row = evaluate_combination(
                matrix, outcome, direction, combo
            )
            # Use CLI threshold for the final status.
            if row["n"] >= args.min_sample and row["win_rate"] is not None:
                row["status"] = (
                    "VALIDATED_80_PLUS"
                    if row["win_rate"] >= args.min_win_rate
                    else "RESEARCH_ONLY"
                )
            patterns.append(row)

    pattern_df = pd.DataFrame(patterns)
    feature_df = pd.DataFrame(feature_rows)

    validated = pattern_df[
        pattern_df["status"].eq("VALIDATED_80_PLUS")
    ].copy()

    # Prefer the strongest validated pattern, but preserve every validated
    # pattern for audit. Do not silently pick one and discard evidence.
    if not validated.empty:
        validated = validated.sort_values(
            ["win_rate", "n", "features"],
            ascending=[False, False, True],
        )

    freeze = {
        "logic_version": "FINAL-1.1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input": str(path),
        "events": int(len(df)),
        "outcome": target_col,
        "direction_source": price_col,
        "minimum_sample": int(args.min_sample),
        "minimum_win_rate": float(args.min_win_rate),
        "maximum_combination_size": MAX_COMBINATION_SIZE,
        "validated_pattern_count": int(len(validated)),
        "validated_patterns": validated.to_dict("records"),
        "rules": [
            "A footprint must be observable before the historical outcome.",
            "Missing values are unavailable, never zero.",
            "Patterns use complete-case evidence only.",
            "No future outcome field is used as a footprint.",
            "No arbitrary weights or composite score are created.",
            "A pattern is frozen only when sample and win-rate gates pass.",
            "A high win rate from a tiny sample is not frozen.",
            "SDL stock qualification remains the final stock-level gate.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pattern_df.to_csv(OUT_PATTERNS, index=False)
    feature_df.to_csv(OUT_FEATURES, index=False)
    OUT_JSON.write_text(
        json.dumps(freeze, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"INPUT: {path}")
    print(f"EVENTS: {len(df)}")
    print(f"OUTCOME: {target_col}")
    print(f"DIRECTION FIELD: {price_col or 'inferred/unavailable'}")
    print(f"FOOTPRINT FIELDS: {', '.join(fields)}")
    print(f"COMBINATIONS TESTED: {len(pattern_df)}")
    print(f"VALIDATED >= {args.min_win_rate:.0%}: {len(validated)}")

    if validated.empty:
        print(
            "RESULT: No pattern currently meets the required "
            f"{args.min_win_rate:.0%} win rate with minimum sample "
            f"{args.min_sample}."
        )
        print(
            "IMPORTANT: This means the current dataset does not yet "
            "support an 80% frozen rule. Do not lower the threshold merely "
            "to obtain a pattern."
        )
    else:
        print("TOP VALIDATED PATTERNS:")
        for _, r in validated.head(10).iterrows():
            print(
                f"  {r['pattern']} | n={int(r['n'])} "
                f"wins={int(r['wins'])} losses={int(r['losses'])} "
                f"win_rate={r['win_rate']:.1%}"
            )

    print(f"PATTERN AUDIT: {OUT_PATTERNS}")
    print(f"FEATURE AUDIT: {OUT_FEATURES}")
    print(f"FREEZE FILE: {OUT_JSON}")


if __name__ == "__main__":
    main()
