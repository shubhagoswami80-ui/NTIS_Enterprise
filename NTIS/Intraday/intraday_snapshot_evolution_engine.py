"""
=========================================================
NTIS Intraday Snapshot Evolution Engine
Version : 1.0

Purpose:
    Track intraday signal changes across snapshots.

Input:
    Intraday scored/probability files from snapshots

Output:
    intraday_signal_evolution.csv

Notes:
    Framework version.
    Designed for multiple intraday uploads:
    Morning / Midday / Closing snapshots.
=========================================================
"""

from pathlib import Path
import pandas as pd
from datetime import datetime


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_probability_analysis.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_signal_evolution.csv"
)


class IntradaySnapshotEvolution:


    def run(self):

        df = pd.read_csv(INPUT_FILE)


        result = df.copy()


        result["Snapshot Time"] = (
            datetime.now()
            .strftime("%H:%M:%S")
        )


        result["Signal Strength"] = "STABLE"


        result.loc[
            result["Intraday Probability %"] >= 80,
            "Signal Strength"
        ] = "STRONG"


        result.loc[
            result["Intraday Probability %"] <= 35,
            "Signal Strength"
        ] = "WEAK"


        columns = [
            "Symbol",
            "Pattern",
            "NTIS Intraday Score",
            "Intraday Probability %",
            "Confidence",
            "Final Bias",
            "Snapshot Time",
            "Signal Strength"
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

    output = IntradaySnapshotEvolution().run()

    print("=" * 60)
    print("INTRADAY SIGNAL EVOLUTION CREATED")
    print(output)
    print("=" * 60)
