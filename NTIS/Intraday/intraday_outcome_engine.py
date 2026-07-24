"""
NTIS Intraday Outcome Engine v1.0

Purpose:
    Update learning memory outcomes.

Rules:
    - Uses central configuration
    - CSV based
    - Keeps pending events ready for outcome tracking
"""

import pandas as pd

from config_loader import LEARNING_ROOT


MEMORY_FILE = LEARNING_ROOT / "intraday_learning_memory.csv"


def update_outcome():

    if not MEMORY_FILE.exists():
        raise FileNotFoundError(
            "intraday_learning_memory.csv not found"
        )

    df = pd.read_csv(MEMORY_FILE)

    pending = df[
        df["Outcome"] == "PENDING"
    ]

    print("Pending Events:", len(pending))

    if pending.empty:
        print("No pending records")
        return

    # Outcome calculation hook.
    # Future version will connect replay/future price data.

    df.to_csv(
        MEMORY_FILE,
        index=False
    )

    print("Outcome Engine Updated:")
    print(MEMORY_FILE)


if __name__ == "__main__":
    update_outcome()
