"""
NTIS Intraday Trade Memory Connector v1.1

Purpose:
    Convert validated trade candidates into NTIS learning memory.

Improvements:
    - Batch processing
    - Single CSV write
    - Duplicate filtering
    - Cleaner execution output
    - No hardcoded paths
"""

from datetime import datetime
import pandas as pd

from config_loader import OUTPUT_ROOT, LEARNING_ROOT


MEMORY_FILE = LEARNING_ROOT / "intraday_learning_memory.csv"


MEMORY_COLUMNS = [
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


def get_latest_trade_file():

    files = list(
        OUTPUT_ROOT.rglob(
            "intraday_trade_candidates.csv"
        )
    )

    if not files:
        raise FileNotFoundError(
            "No intraday_trade_candidates.csv found"
        )

    return max(
        files,
        key=lambda x: x.stat().st_mtime
    )


def get_value(row, possible_columns):

    for col in possible_columns:

        if col in row.index:
            return row[col]

    return None


def build_memory_events(df):

    events = []

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

        events.append(event)

    return pd.DataFrame(events)


def update_memory():

    trade_file = get_latest_trade_file()

    print("Reading Trade File:")
    print(trade_file)


    trades = pd.read_csv(
        trade_file
    )


    new_events = build_memory_events(
        trades
    )


    MEMORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    if MEMORY_FILE.exists():

        old_memory = pd.read_csv(
            MEMORY_FILE
        )

        combined = pd.concat(
            [
                old_memory,
                new_events
            ],
            ignore_index=True
        )

    else:

        combined = new_events


    before = len(combined)


    combined = combined.drop_duplicates(
        subset=[
            "Date",
            "Snapshot_Time",
            "Symbol",
            "Pattern"
        ]
    )


    after = len(combined)


    combined.to_csv(
        MEMORY_FILE,
        index=False
    )


    print()
    print(
        "Trade Events Found :",
        len(trades)
    )

    print(
        "New Memory Events :",
        after
    )

    print(
        "Duplicates Removed:",
        before - after
    )

    print(
        "Learning Memory Updated:"
    )

    print(
        MEMORY_FILE
    )


if __name__ == "__main__":

    update_memory()