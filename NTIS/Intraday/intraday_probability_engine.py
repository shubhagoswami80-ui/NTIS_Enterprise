from datetime import datetime
"""
=========================================================
NTIS Intraday Probability Engine
Version : 1.0

Purpose:
    Convert Intraday score + pattern into probability.

Input:
    intraday_pattern_analysis.csv

Output:
    intraday_probability_analysis.csv

Independent Intraday Module
=========================================================
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_pattern_analysis.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_probability_analysis.csv"
)


class IntradayProbabilityEngine:


    def pattern_probability(self, pattern):

        mapping = {

            "Fresh Long Buildup": 75,
            "Short Covering": 70,
            "Futures Long Setup": 75,
            "Volume Expansion": 60,
            "Short Buildup": 35,
            "Long Unwinding": 30,
            "Futures Short Setup": 30,
            "Neutral": 50
        }

        return mapping.get(
            pattern,
            50
        )


    def calculate_probability(self, row):

        score = row.get(
            "NTIS Intraday Score",
            0
        )

        pattern = row.get(
            "Pattern",
            "Neutral"
        )

        base = self.pattern_probability(
            pattern
        )

        adjustment = 0

        if score >= 70:
            adjustment += 15

        elif score >= 50:
            adjustment += 5

        elif score < 30:
            adjustment -= 15


        probability = base + adjustment

        probability = max(
            10,
            min(
                probability,
                95
            )
        )

        return probability


    def confidence(self, probability):

        if probability >= 75:
            return "HIGH"

        elif probability >= 55:
            return "MEDIUM"

        return "LOW"


    def run(self):

        df = pd.read_csv(
            INPUT_FILE
        )


        df["Intraday Probability %"] = (
            df.apply(
                self.calculate_probability,
                axis=1
            )
        )


        df["Confidence"] = (
            df["Intraday Probability %"]
            .apply(
                self.confidence
            )
        )


        df["Final Bias"] = "NEUTRAL"

        df.loc[
            df["Intraday Probability %"] >= 70,
            "Final Bias"
        ] = "BUY"


        df.loc[
            df["Intraday Probability %"] <= 35,
            "Final Bias"
        ] = "SELL"


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

    result = IntradayProbabilityEngine().run()

    print("=" * 60)
    print("INTRADAY PROBABILITY COMPLETE")
    print(result)
    print("=" * 60)
