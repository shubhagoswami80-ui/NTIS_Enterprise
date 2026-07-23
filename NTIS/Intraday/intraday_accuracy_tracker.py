"""
=========================================================
NTIS Intraday Accuracy Tracker
Version : 1.0

Purpose:
    Track intraday prediction outcomes.

Input:
    intraday_trade_candidates.csv

Output:
    intraday_accuracy_report.csv

Notes:
    - Initial framework
    - Outcome calculation placeholder
    - Designed for future historical validation
=========================================================
"""

from pathlib import Path
from datetime import datetime
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_trade_candidates.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_accuracy_report.csv"
)


class IntradayAccuracyTracker:


    def run(self):

        df = pd.read_csv(
            INPUT_FILE
        )


        result = df.copy()


        result["Analysis Date"] = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )


        # Future actual market data fields
        result["Actual Close"] = None
        result["Outcome"] = "PENDING"
        result["Points"] = None
        result["Accuracy"] = 0


        columns = [
            "Analysis Date",
            "Symbol",
            "Pattern",
            "Intraday Probability %",
            "Final Bias",
            "Entry Price",
            "Stop Loss",
            "Target",
            "Actual Close",
            "Outcome",
            "Points",
            "Accuracy"
        ]


        result = result[
            [c for c in columns if c in result.columns]
        ]


        result.to_csv(
            OUTPUT_FILE,
            index=False
        )


        return OUTPUT_FILE



if __name__ == "__main__":

    output = IntradayAccuracyTracker().run()

    print("=" * 60)
    print("INTRADAY ACCURACY REPORT CREATED")
    print(output)
    print("=" * 60)
