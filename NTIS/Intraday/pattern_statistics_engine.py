"""
===========================================================
NTIS Pattern Statistics Engine
Version : 1.1

Purpose:
    Convert intraday learning memory into
    compressed intelligence statistics.

Input:
    intraday_learning_memory.csv

Output:
    pattern_statistics.csv

Update:
    Added outcome normalization:
        TARGET HIT  -> SUCCESS
        STOP LOSS HIT -> FAILED
        EOD EXIT -> Based on Return %

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
# OUTCOME NORMALIZER
# ============================================================

def normalize_outcome(row):

    outcome = str(
        row.get(
            "Outcome",
            "PENDING"
        )
    )


    if outcome == "TARGET HIT":

        return "SUCCESS"


    if outcome == "STOP LOSS HIT":

        return "FAILED"


    if outcome == "EOD EXIT":

        try:

            return (
                "SUCCESS"
                if float(
                    row.get(
                        "Future_Move_%",
                        0
                    )
                ) > 0
                else
                "FAILED"
            )

        except:

            return "PENDING"


    if outcome in [
        "SUCCESS",
        "FAILED"
    ]:

        return outcome


    return "PENDING"



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


    df["Normalized_Outcome"] = (
        df.apply(
            normalize_outcome,
            axis=1
        )
    )


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
                "Normalized_Outcome",
                lambda x:
                (
                    x == "SUCCESS"
                ).sum()
            ),

            Failed_Trades=(
                "Normalized_Outcome",
                lambda x:
                (
                    x == "FAILED"
                ).sum()
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