"""
NTIS Intraday Learning Memory Builder v1.0

Purpose:
    Store important trade situations and outcomes.

Principle:
    NTIS remembers trade situations and results,
    not every market data point.

Rules:
    - No hardcoded paths
    - Uses config_loader.py
    - CSV based memory
    - No database
"""

from pathlib import Path
from datetime import datetime
import pandas as pd

from config_loader import LEARNING_ROOT


# ============================================================
# OUTPUT FILE
# ============================================================

MEMORY_FILE = (
    LEARNING_ROOT /
    "intraday_learning_memory.csv"
)


# ============================================================
# MEMORY SCHEMA
# ============================================================

COLUMNS = [

    "Date",
    "Snapshot_Time",
    "Symbol",

    "Direction",
    "Pattern",

    "NTIS_Score",
    "Probability",
    "Confidence",

    "Entry_Price",

    "Previous_Close",
    "Previous_High",
    "Previous_Low",

    "Price_Condition",
    "OI_Condition",
    "Volume_Condition",
    "IV_Condition",

    "Trade_Reason",

    "Outcome",
    "Future_Move_%",

    "Target_Hit",
    "Stop_Loss_Hit"

]


# ============================================================
# DUPLICATE CHECK
# ============================================================

def is_duplicate(record):

    if not MEMORY_FILE.exists():

        return False


    df = pd.read_csv(
        MEMORY_FILE
    )


    if df.empty:

        return False


    match = df[
        (df["Date"] == record["Date"]) &
        (df["Symbol"] == record["Symbol"]) &
        (df["Snapshot_Time"] == record["Snapshot_Time"]) &
        (df["Pattern"] == record["Pattern"])
    ]


    return not match.empty



# ============================================================
# SAVE MEMORY EVENT
# ============================================================

def save_memory_event(record):


    for col in COLUMNS:

        if col not in record:

            record[col] = None


    if is_duplicate(record):

        print(
            "Duplicate event skipped:",
            record["Symbol"]
        )

        return


    new_row = pd.DataFrame(
        [record],
        columns=COLUMNS
    )


    if MEMORY_FILE.exists():

        old = pd.read_csv(
            MEMORY_FILE
        )

        final = pd.concat(
            [
                old,
                new_row
            ],
            ignore_index=True
        )

    else:

        final = new_row


    final.to_csv(
        MEMORY_FILE,
        index=False
    )


    print(
        "Learning Memory Updated:",
        MEMORY_FILE
    )



# ============================================================
# TEST EVENT
# ============================================================

if __name__ == "__main__":


    test_event = {

        "Date":
            datetime.today().strftime("%Y-%m-%d"),

        "Snapshot_Time":
            datetime.today().strftime("%H:%M"),

        "Symbol":
            "TEST",

        "Direction":
            "BUY",

        "Pattern":
            "Fresh Long Buildup",

        "NTIS_Score":
            78,

        "Probability":
            82,

        "Confidence":
            "HIGH",

        "Entry_Price":
            1000,

        "Previous_Close":
            980,

        "Previous_High":
            990,

        "Previous_Low":
            970,

        "Price_Condition":
            "Above Previous High",

        "OI_Condition":
            "Positive",

        "Volume_Condition":
            "Expansion",

        "IV_Condition":
            "Stable",

        "Trade_Reason":
            "Price breakout with OI confirmation",

        "Outcome":
            "PENDING"

    }


    save_memory_event(
        test_event
    )