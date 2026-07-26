"""
NTIS Intraday Accuracy Tracker v2.0

Creates accuracy summary from replay results.
"""

from pathlib import Path
import pandas as pd


def create_accuracy_report(
    replay_file
):

    replay_file = Path(replay_file)

    df = pd.read_csv(
        replay_file
    )

    if "Outcome" not in df.columns:
        raise KeyError(
            "Outcome column missing"
        )

    df["Accuracy"] = (
        df["Outcome"]
        .isin(
            [
                "TARGET HIT"
            ]
        )
        .astype(int)
        * 100
    )

    output = (
        replay_file.parent /
        "intraday_accuracy_report.csv"
    )

    df.to_csv(
        output,
        index=False
    )

    return output
