from datetime import datetime
"""
=========================================================
NTIS Intraday Pattern Engine
Version : 1.0

Purpose:
    Convert intraday scores and market behaviour
    into trading patterns.

Input:
    intraday_scored_stocks.csv

Output:
    intraday_pattern_analysis.csv

Independent Intraday Module
=========================================================
"""

from pathlib import Path
import pandas as pd
from intraday_config import OUTPUT_FOLDER


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_scored_stocks.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_pattern_analysis.csv"
)


class IntradayPatternEngine:


    def identify_pattern(self, row):

        price = row.get("Price Chg %")
        oi = row.get("OI Chg %")
        fut = str(row.get("Fut Buildup"))
        volume = row.get("Volume Chg %")


        if pd.notna(price) and pd.notna(oi):

            if price > 0 and oi > 0:
                return "Fresh Long Buildup"

            if price < 0 and oi > 0:
                return "Short Buildup"

            if price > 0 and oi < 0:
                return "Short Covering"

            if price < 0 and oi < 0:
                return "Long Unwinding"


        if pd.notna(volume) and volume > 100:
            return "Volume Expansion"


        if "long" in fut.lower():
            return "Futures Long Setup"

        if "short" in fut.lower():
            return "Futures Short Setup"


        return "Neutral"


    def run(self):

        df = pd.read_csv(INPUT_FILE)

        df["Pattern"] = df.apply(
            self.identify_pattern,
            axis=1
        )


        df.to_csv(
            OUTPUT_FILE,
            index=False
        )

        return OUTPUT_FILE



if __name__ == "__main__":

    result = IntradayPatternEngine().run()

    print("=" * 60)
    print("INTRADAY PATTERN ANALYSIS COMPLETE")
    print(result)
    print("=" * 60)