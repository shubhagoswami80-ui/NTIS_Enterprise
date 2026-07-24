"""
NTIS Pattern Statistics Engine v1.0

Purpose:
    Convert intraday learning memory into
    compressed intelligence statistics.

Principle:
    NTIS remembers patterns and outcomes,
    not raw market points.

Input:
    Intraday Learning Memory

Output:
    Pattern Statistics

Rules:
    - No EOD changes
    - No dashboard changes
    - Uses central configuration
    - CSV based
"""

from pathlib import Path
import pandas as pd

from config_loader import LEARNING_ROOT


# ============================================================
# PATHS
# ============================================================

INTELLIGENCE_ROOT = (
    LEARNING_ROOT.parent /
    "Intelligence"
)

INTELLIGENCE_ROOT.mkdir(
    parents=True,
    exist_ok=True
)


MEMORY_FILE = (
    LEARNING_ROOT /
    "intraday_learning_memory.csv"
)


OUTPUT_FILE = (
    INTELLIGENCE_ROOT /
    "pattern_statistics.csv"
)


# ============================================================
# BUILD STATISTICS
# ============================================================

def build_pattern_statistics():

    if not MEMORY_FILE.exists():

        raise FileNotFoundError(
            "Learning memory file not found"
        )


    df = pd.read_csv(
        MEMORY_FILE
    )


    if df.empty:

        print(
            "Learning memory is empty"
        )

        return


    df = df[
        df["Pattern"].notna()
    ]


    statistics = (

        df
        .groupby(
            [
                "Pattern",
                "Direction"
            ],
            dropna=False
        )
        .agg(

            Occurrences=(
                "Symbol",
                "count"
            ),

            Successful_Trades=(
                "Outcome",
                lambda x:
                (x == "SUCCESS").sum()
            ),

            Failed_Trades=(
                "Outcome",
                lambda x:
                (x == "FAILED").sum()
            )

        )
        .reset_index()

    )


    statistics["Pending_Trades"] = (

        statistics["Occurrences"]
        -
        statistics["Successful_Trades"]
        -
        statistics["Failed_Trades"]

    )


    statistics["Success_%"] = (

        (
            statistics["Successful_Trades"]
            /
            statistics["Occurrences"]
        )
        *
        100

    ).round(2)


    statistics.to_csv(
        OUTPUT_FILE,
        index=False
    )


    print(
        "Pattern Statistics Created:"
    )

    print(
        OUTPUT_FILE
    )

    print(
        statistics.head()
    )



# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    build_pattern_statistics()