"""
===========================================================
NTIS Pattern Statistics Engine
Version : 2.0

Purpose:
    Derive historical intelligence statistics from the
    Pattern Intelligence Repository (READ-ONLY view).

Input:
    intraday_pattern_repository.csv

Output:
    pattern_statistics.csv
===========================================================
"""

from pathlib import Path
import pandas as pd

from config_loader import LEARNING_ROOT
from intraday_pattern_repository import IntradayPatternRepository


INTELLIGENCE_ROOT = LEARNING_ROOT.parent / "Intelligence"
OUTPUT_FILE = INTELLIGENCE_ROOT / "pattern_statistics.csv"

STATISTICS_COLUMNS = (
    "Pattern",
    "Direction",
    "Occurrences",
    "Successful_Trades",
    "Failed_Trades",
    "Pending_Trades",
    "Success_%",
)


def _empty_statistics():
    return pd.DataFrame(columns=STATISTICS_COLUMNS)


def build_pattern_statistics():
    """Build and save pattern-level historical performance statistics from Pattern Repository."""
    repo = IntradayPatternRepository()
    repo_df = repo.repo_df

    INTELLIGENCE_ROOT.mkdir(parents=True, exist_ok=True)

    if repo_df.empty:
        statistics = _empty_statistics()
    else:
        # Map repository fields to pattern statistics view schema
        # Group by Pattern_Name and Direction to aggregate across symbols
        df = repo_df.copy()
        
        # Ensure correct types
        df["Occurrences"] = pd.to_numeric(df["Occurrences"], errors="coerce").fillna(0)
        df["Successful_Trades"] = pd.to_numeric(df["Successful_Trades"], errors="coerce").fillna(0)
        df["Failed_Trades"] = pd.to_numeric(df["Failed_Trades"], errors="coerce").fillna(0)
        
        if "Pattern_Name" not in df.columns:
            df["Pattern_Name"] = df.get("Pattern", "Neutral")

        statistics = (
            df.groupby(
                ["Pattern_Name", "Direction"],
                dropna=False,
            )
            .agg(
                Occurrences=("Occurrences", "sum"),
                Successful_Trades=("Successful_Trades", "sum"),
                Failed_Trades=("Failed_Trades", "sum"),
            )
            .reset_index()
        )

        statistics = statistics.rename(columns={"Pattern_Name": "Pattern"})

        statistics["Pending_Trades"] = (
            statistics["Occurrences"]
            - statistics["Successful_Trades"]
            - statistics["Failed_Trades"]
        ).clip(lower=0)

        statistics["Success_%"] = (
            statistics["Successful_Trades"]
            .div(statistics["Occurrences"].replace(0, 1))
            .mul(100)
            .round(2)
        )

    statistics.to_csv(OUTPUT_FILE, index=False)

    print("Pattern Statistics Created (from Repository):")
    print(OUTPUT_FILE)
    print(statistics.head())

    return OUTPUT_FILE


if __name__ == "__main__":
    build_pattern_statistics()
