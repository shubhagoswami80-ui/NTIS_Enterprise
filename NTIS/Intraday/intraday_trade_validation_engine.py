"""
=========================================================
NTIS Intraday Trade Validation Engine
Version : 1.0

Purpose:
    Convert probability output into trade candidates.

Input:
    intraday_probability_analysis.csv

Output:
    intraday_trade_candidates.csv

Independent Intraday Module
=========================================================
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_probability_analysis.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_trade_candidates.csv"
)


class IntradayTradeValidationEngine:


    def validate_signal(self, row):

        probability = row.get(
            "Intraday Probability %",
            0
        )

        pattern = str(
            row.get("Pattern", "")
        )

        score = row.get(
            "NTIS Intraday Score",
            0
        )


        if (
            probability >= 75
            and score >= 35
            and "Short" not in pattern
            and "Unwinding" not in pattern
        ):
            return "VALID BUY"


        if (
            probability <= 35
            and score <= 30
        ):
            return "VALID SELL"


        return "WATCH"


    def risk_level(self, row):

        probability = row.get(
            "Intraday Probability %",
            0
        )

        if probability >= 80:
            return "LOW"

        elif probability >= 60:
            return "MEDIUM"

        return "HIGH"


    def run(self):

        df = pd.read_csv(
            INPUT_FILE
        )


        df["Validation Signal"] = df.apply(
            self.validate_signal,
            axis=1
        )


        df["Risk Level"] = df.apply(
            self.risk_level,
            axis=1
        )


        df["Entry Price"] = df.get(
            "Price"
        )


        df["Stop Loss"] = (
            df["Entry Price"] * 0.98
        )


        df["Target"] = (
            df["Entry Price"] * 1.04
        )


        df = df.sort_values(
            "Intraday Probability %",
            ascending=False
        )


        df.to_csv(
            OUTPUT_FILE,
            index=False
        )


        return OUTPUT_FILE



if __name__ == "__main__":

    result = IntradayTradeValidationEngine().run()

    print("=" * 60)
    print("INTRADAY TRADE VALIDATION COMPLETE")
    print(result)
    print("=" * 60)
