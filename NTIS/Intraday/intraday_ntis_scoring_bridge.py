"""
from intraday_config import OUTPUT_FOLDER
NTIS Intraday Scoring Bridge
Version: 1.0

Purpose:
Adapter layer only.
Connects Intraday master with scoring logic later.
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    OUTPUT_FOLDER / "intraday_market_master_ntis.csv"
)

OUTPUT_FILE = Path(
    OUTPUT_FOLDER / "intraday_scoring_input.csv"
)


def build_scoring_input():

    df = pd.read_csv(INPUT_FILE)

    df["NTIS_READY"] = True

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    return OUTPUT_FILE


if __name__ == "__main__":

    print(build_scoring_input())
