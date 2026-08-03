"""
NTIS-EOD Pipeline Validator v1.0

Bundle 01 - Platform Stabilization

Purpose:
    Read-only validation of frozen NTIS execution pipeline.

Checks:
    - Pipeline component order
    - Required artifact presence

Does not execute engines.
"""

from pathlib import Path
import csv
from datetime import datetime


BASE = Path(r"E:/NSE_Daily_Analysis")

OUTPUT = (
    BASE /
    "NTIS" /
    "tools" /
    "Architecture_Report"
)

OUTPUT.mkdir(
    parents=True,
    exist_ok=True
)


PIPELINE = [
    (
        "Scoring Engine",
        BASE / "Output" / "market_master.csv",
        BASE / "Output" / "ntis_ranked_stocks.csv"
    ),
    (
        "Pattern Engine",
        BASE / "Output" / "ntis_ranked_stocks.csv",
        BASE / "Output" / "ntis_pattern_analysis.csv"
    ),
    (
        "Probability Engine",
        BASE / "Output" / "ntis_pattern_analysis.csv",
        BASE / "Output" / "ntis_probability_analysis.csv"
    ),
    (
        "Trade Validation",
        BASE / "Output" / "ntis_probability_analysis.csv",
        BASE / "Output" / "ntis_trade_candidates.csv"
    )
]


def main():

    rows = []

    for name, input_file, output_file in PIPELINE:

        rows.append(
            [
                name,
                str(input_file),
                input_file.exists(),
                str(output_file),
                output_file.exists()
            ]
        )

    report = OUTPUT / "NTIS_Pipeline_Validation.csv"

    with open(
        report,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(
            [
                "Engine",
                "Input",
                "Input Available",
                "Output",
                "Output Available"
            ]
        )

        writer.writerows(rows)

    print("NTIS Pipeline Validation Completed")
    print(datetime.now())
    print(report)


if __name__ == "__main__":
    main()
