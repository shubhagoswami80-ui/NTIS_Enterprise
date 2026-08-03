"""
NTIS-EOD Engine Ownership Map v1.0

Bundle 01 - Platform Stabilization

Creates a frozen ownership reference for NTIS engines.
Read-only utility.
"""

from pathlib import Path
import csv
from datetime import datetime

OUTPUT = Path(
    r"E:/NSE_Daily_Analysis/NTIS/tools/Architecture_Report"
)

OUTPUT.mkdir(
    parents=True,
    exist_ok=True
)

OWNERSHIP = [
    [
        "Importer",
        "Data ingestion",
        "Raw EOD / market data",
        "Market Master"
    ],
    [
        "Scoring Engine",
        "Technical scoring and ranking",
        "market_master.csv",
        "ntis_ranked_stocks.csv"
    ],
    [
        "Pattern Engine",
        "Pattern identification",
        "ntis_ranked_stocks.csv",
        "ntis_pattern_analysis.csv"
    ],
    [
        "Probability Engine",
        "Statistical probability calculation",
        "ntis_pattern_analysis.csv",
        "ntis_probability_analysis.csv"
    ],
    [
        "Similarity Engine",
        "Historical intelligence",
        "Probability output",
        "Historical evidence"
    ],
    [
        "Trade Validation",
        "Trade candidate validation",
        "Probability analysis",
        "ntis_trade_candidates.csv"
    ],
    [
        "History Manager",
        "Archive and learning records",
        "Validated intelligence",
        "Historical database"
    ],
    [
        "Dashboard",
        "Presentation layer",
        "Validated outputs",
        "User interface"
    ]
]


def main():

    output = OUTPUT / "NTIS_Engine_Ownership_Map.csv"

    with open(
        output,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                "Engine",
                "Responsibility",
                "Input",
                "Output"
            ]
        )

        writer.writerows(
            OWNERSHIP
        )

    print("Created:")
    print(output)
    print(datetime.now())


if __name__ == "__main__":
    main()
