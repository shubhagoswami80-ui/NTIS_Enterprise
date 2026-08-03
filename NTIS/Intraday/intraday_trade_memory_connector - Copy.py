"""
NTIS Intraday Trade Memory Connector v1.0

Purpose:
    Convert validated trade candidates into
    NTIS learning memory events.

Principle:
    Store trade situations and outcomes,
    not every market data point.

Rules:
    - No hardcoded paths
    - Uses central configuration
    - Does not calculate signals
    - Only records decisions
"""

from pathlib import Path
from datetime import datetime
import pandas as pd

from config_loader import OUTPUT_ROOT

from intraday_learning_memory_builder import save_memory_event


# ============================================================
# INPUT FILE
# ============================================================

def get_latest_trade_file():

    files = list(
        OUTPUT_ROOT.rglob(
            "intraday_trade_candidates.csv"
        )
    )

    if not files:
        raise FileNotFoundError(
            "No trade candidate file found"
        )

    return max(
        files,
        key=lambda x: x.stat().st_mtime
    )


# ============================================================
# COLUMN SAFE READER
# ============================================================

def get_value(row, columns, default=None):

    for col in columns:

        if col in row.index:

            return row[col]

    return default



# ============================================================
# CONVERT TRADE TO MEMORY EVENT
# ============================================================

def process_trade_memory():

    trade_file = get_latest_trade_file()

    print(
        "Reading Trade File:",
        trade_file
    )


    df = pd.read_csv(
        trade_file
    )


    for _, row in df.iterrows():


        event = {

            "Date":
                datetime.today().strftime("%Y-%m-%d"),


            "Snapshot_Time":
                datetime.today().strftime("%H:%M"),


            "Symbol":
                get_value(
                    row,
                    ["Symbol"]
                ),


            "Direction":
                get_value(
                    row,
                    [
                        "Final Signal",
                        "Validation Signal",
                        "Trade Bias"
                    ]
                ),


            "Pattern":
                get_value(
                    row,
                    ["Pattern"]
                ),


            "NTIS_Score":
                get_value(
                    row,
                    [
                        "NTIS Score",
                        "NTIS Intraday Score"
                    ]
                ),


            "Probability":
                get_value(
                    row,
                    [
                        "Probability",
                        "Intraday Probability %",
                        "BUY Probability %"
                    ]
                ),


            "Confidence":
                get_value(
                    row,
                    ["Confidence"]
                ),


            "Entry_Price":
                get_value(
                    row,
                    [
                        "Entry Price",
                        "Entry Close"
                    ]
                ),


            "Trade_Reason":
                get_value(
                    row,
                    [
                        "Reason",
                        "Trade Reason"
                    ]
                ),


            "Outcome":
                "PENDING"

        }


        save_memory_event(
            event
        )



# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    process_trade_memory()