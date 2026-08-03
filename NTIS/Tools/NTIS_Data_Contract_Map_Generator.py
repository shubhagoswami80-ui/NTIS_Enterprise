"""
NTIS-EOD Data Contract Map Generator v1.0

Bundle 01 - Platform Stabilization

Creates canonical input/output contracts.
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

CONTRACTS = [
    [
        "Market Master",
        "market_master.csv",
        "Symbol, CMP, Price Chg %, OI Chg %, Volume Chg (%)",
        "Scoring Engine input"
    ],
    [
        "Ranked Stocks",
        "ntis_ranked_stocks.csv",
        "Symbol, NTIS Score, Signal, Rank",
        "Pattern Engine input"
    ],
    [
        "Pattern Analysis",
        "ntis_pattern_analysis.csv",
        "Symbol, Pattern, Pattern Reason",
        "Probability Engine input"
    ],
    [
        "Probability Analysis",
        "ntis_probability_analysis.csv",
        "Probability, Confidence, Trade Bias",
        "Similarity / Trade Validation input"
    ],
    [
        "Trade Candidates",
        "ntis_trade_candidates.csv",
        "Symbol, Final Signal, Entry, Stop Loss, Target",
        "Trading intelligence output"
    ],
    [
        "Outcome Report",
        "ntis_outcome_report.csv",
        "Actual Return %, Outcome, Accuracy",
        "Learning and validation"
    ]
]


def main():

    output = OUTPUT / "NTIS_Data_Contract_Map.csv"

    with open(
        output,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(
            [
                "Data Object",
                "File",
                "Contract Fields",
                "Consumer"
            ]
        )

        writer.writerows(CONTRACTS)

    print("Created:")
    print(output)
    print(datetime.now())


if __name__ == "__main__":
    main()
