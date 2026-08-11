# ----------------------------------------------------------------------
# Bundle 01 - Step 3
# File:
#     intraday_learning_memory_builder.py
#
# Purpose:
#     Build learning memory preserving Pattern Intelligence.
# ----------------------------------------------------------------------

from pathlib import Path
from datetime import datetime

import pandas as pd


LEARNING_COLUMNS = [

    "Trade_Date",
    "Snapshot_Time",

    "Symbol",

    "Pattern",
    "Pattern_DNA",
    "Pattern_ID",

    "Direction",

    "NTIS_Score",

    "Probability",

    "Confidence",

    "Entry_Price",

    "Exit_Price",

    "Outcome",

    "PnL",

    "Trade_Reason"

]


def build_learning_memory(df):

    for column in LEARNING_COLUMNS:

        if column not in df.columns:

            df[column] = ""

    learning_df = df[
        LEARNING_COLUMNS
    ].copy()

    learning_df["Learning_Timestamp"] = (
        datetime.now()
        .strftime("%Y-%m-%d %H:%M:%S")
    )

    return learning_df


def append_learning_memory(

        learning_df,
        memory_file

):

    memory_file = Path(memory_file)

    if memory_file.exists():

        existing = pd.read_csv(
            memory_file
        )

        learning_df = pd.concat(

            [
                existing,
                learning_df
            ],

            ignore_index=True

        )

    learning_df.to_csv(

        memory_file,

        index=False

    )

    return memory_file