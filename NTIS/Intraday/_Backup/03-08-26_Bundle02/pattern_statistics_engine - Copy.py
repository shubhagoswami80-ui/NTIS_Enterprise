"""
===========================================================
NTIS Pattern Statistics Engine
Version : 1.2

Purpose:
    Convert intraday learning memory into compressed
    historical intelligence statistics.

Input:
    intraday_learning_memory.csv

Output:
    pattern_statistics.csv

Outcome normalization:
    TARGET HIT    -> SUCCESS
    STOP LOSS HIT -> FAILED
    EOD EXIT      -> Based on Future_Move_%

Rules:
    - No EOD changes
    - No dashboard changes
    - Uses central configuration
    - CSV based
===========================================================
"""

from pathlib import Path

import pandas as pd

from config_loader import LEARNING_ROOT


# ============================================================
# PATHS
# ============================================================

INTELLIGENCE_ROOT = LEARNING_ROOT.parent / "Intelligence"

MEMORY_FILE = LEARNING_ROOT / "intraday_learning_memory.csv"

OUTPUT_FILE = INTELLIGENCE_ROOT / "pattern_statistics.csv"


REQUIRED_COLUMNS = (
    "Symbol",
    "Pattern",
    "Direction",
    "Outcome",
)


STATISTICS_COLUMNS = (
    "Pattern",
    "Direction",
    "Occurrences",
    "Successful_Trades",
    "Failed_Trades",
    "Pending_Trades",
    "Success_%",
)


# ============================================================
# OUTCOME NORMALIZER
# ============================================================

def normalize_outcome(row):
    """Return the normalized historical outcome for one memory record."""

    outcome = str(row.get("Outcome", "PENDING")).strip().upper()

    if outcome == "TARGET HIT":
        return "SUCCESS"

    if outcome == "STOP LOSS HIT":
        return "FAILED"

    if outcome == "EOD EXIT":
        try:
            return (
                "SUCCESS"
                if float(row.get("Future_Move_%", 0)) > 0
                else "FAILED"
            )
        except (TypeError, ValueError):
            return "PENDING"

    if outcome in {"SUCCESS", "FAILED"}:
        return outcome

    return "PENDING"


# ============================================================
# BUILD STATISTICS
# ============================================================

def _validate_memory_columns(df):
    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise KeyError(
            "Learning memory missing required columns: "
            + ", ".join(missing_columns)
        )


def _empty_statistics():
    return pd.DataFrame(columns=STATISTICS_COLUMNS)


def build_pattern_statistics():
    """Build and save pattern-level historical performance statistics."""

    if not MEMORY_FILE.exists():
        raise FileNotFoundError(
            f"Learning memory file not found: {MEMORY_FILE}"
        )

    df = pd.read_csv(MEMORY_FILE)

    _validate_memory_columns(df)

    INTELLIGENCE_ROOT.mkdir(parents=True, exist_ok=True)

    if df.empty:
        statistics = _empty_statistics()
    else:
        df = df[df["Pattern"].notna()].copy()

        if df.empty:
            statistics = _empty_statistics()
        else:
            df["Normalized_Outcome"] = df.apply(
                normalize_outcome,
                axis=1,
            )

            statistics = (
                df.groupby(
                    ["Pattern", "Direction"],
                    dropna=False,
                )
                .agg(
                    Occurrences=("Symbol", "count"),
                    Successful_Trades=(
                        "Normalized_Outcome",
                        lambda values: (values == "SUCCESS").sum(),
                    ),
                    Failed_Trades=(
                        "Normalized_Outcome",
                        lambda values: (values == "FAILED").sum(),
                    ),
                )
                .reset_index()
            )

            statistics["Pending_Trades"] = (
                statistics["Occurrences"]
                - statistics["Successful_Trades"]
                - statistics["Failed_Trades"]
            )

            statistics["Success_%"] = (
                statistics["Successful_Trades"]
                .div(statistics["Occurrences"])
                .mul(100)
                .round(2)
            )

    statistics.to_csv(OUTPUT_FILE, index=False)

    print("Pattern Statistics Created:")
    print(OUTPUT_FILE)
    print(statistics.head())

    return OUTPUT_FILE


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    build_pattern_statistics()
