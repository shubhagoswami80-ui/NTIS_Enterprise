"""
=========================================================
NTIS Replay Report
Version : 1.0
Purpose :
    Generate Replay Reports
=========================================================
"""

from pathlib import Path

import pandas as pd


class ReplayReport:

    def __init__(self):
        pass

    @staticmethod
    def save_results(df, output_file):

        output_file = Path(output_file)

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        df.to_csv(
            output_file,
            index=False
        )

    @staticmethod
    def save_summary(summary, output_file):

        output_file = Path(output_file)

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        pd.DataFrame(
            [summary]
        ).to_csv(
            output_file,
            index=False
        )

    @staticmethod
    def print_summary(summary):

        print("\n" + "=" * 55)
        print("NTIS HISTORICAL REPLAY SUMMARY")
        print("=" * 55)

        for key, value in summary.items():
            print(f"{key:<25}: {value}")

        print("=" * 55)