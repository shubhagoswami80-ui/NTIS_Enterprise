"""
=========================================================
NTIS Intraday Probability Calibration Engine
Version : 1.0

Purpose:
    Analyse historical intraday outcomes and prepare
    probability calibration framework.

Input:
    intraday_backtest_results.csv

Output:
    intraday_probability_calibration.csv

Notes:
    Framework version.
    Future versions will calculate accuracy after
    actual market outcomes are connected.
=========================================================
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_backtest_results.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_probability_calibration.csv"
)


class IntradayProbabilityCalibration:


    def run(self):

        df = pd.read_csv(
            INPUT_FILE
        )


        if "Pattern" in df.columns:

            calibration = (
                df.groupby("Pattern")
                .agg(
                    Signals=("Pattern", "count")
                )
                .reset_index()
            )

        else:

            calibration = pd.DataFrame(
                columns=[
                    "Pattern",
                    "Signals"
                ]
            )


        calibration["Successful Signals"] = 0
        calibration["Accuracy %"] = 0
        calibration["Original Probability"] = 0
        calibration["Adjusted Probability"] = 0
        calibration["Confidence Adjustment"] = "PENDING"


        calibration.to_csv(
            OUTPUT_FILE,
            index=False
        )


        return OUTPUT_FILE



if __name__ == "__main__":

    output = IntradayProbabilityCalibration().run()

    print("=" * 60)
    print("INTRADAY PROBABILITY CALIBRATION CREATED")
    print(output)
    print("=" * 60)
