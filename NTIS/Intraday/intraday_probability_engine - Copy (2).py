"""
=========================================================
NTIS Intraday Probability Engine
Version : 1.2

Purpose:
    Convert Intraday score + pattern into probability.

Input:
    intraday_pattern_analysis.csv

Learning Input:
    pattern_statistics.csv

Output:
    intraday_probability_analysis.csv

Update:
    - Added historical pattern performance adjustment
    - Preserves existing scoring logic
    - Uses central dynamic Intraday output path
=========================================================
"""

from pathlib import Path
import pandas as pd

from intraday_path_config import get_today_output
from config_loader import LEARNING_ROOT



OUTPUT_FOLDER = get_today_output()


INPUT_FILE = (
    OUTPUT_FOLDER
    /
    "intraday_pattern_analysis.csv"
)


OUTPUT_FILE = (
    OUTPUT_FOLDER
    /
    "intraday_probability_analysis.csv"
)


STATISTICS_FILE = (
    LEARNING_ROOT.parent
    /
    "Intelligence"
    /
    "pattern_statistics.csv"
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



    def load_pattern_learning(self):

        if not STATISTICS_FILE.exists():

            return {}


        stats = pd.read_csv(
            STATISTICS_FILE
        )


        learning = {}


        for _, row in stats.iterrows():

            pattern = row.get(
                "Pattern"
            )

            success = row.get(
                "Success_%",
                0
            )


            if pd.notna(pattern):

                learning[pattern] = success



        return learning



    def learning_adjustment(
        self,
        pattern,
        learning
    ):

        success = learning.get(
            pattern,
            None
        )


        if success is None:

            return 0


        if success >= 60:

            return 10


        if success >= 40:

            return 5


        if success < 15:

            return -5


        return 0



    def calculate_probability(
        self,
        row,
        learning
    ):

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



        adjustment += self.learning_adjustment(
            pattern,
            learning
        )



        probability = (
            base
            +
            adjustment
        )


        probability = max(
            10,
            min(
                probability,
                95
            )
        )


        return probability



    def confidence(
        self,
        probability
    ):

        if probability >= 75:

            return "HIGH"


        elif probability >= 55:

            return "MEDIUM"


        return "LOW"



    def run(self):


        df = pd.read_csv(
            INPUT_FILE
        )


        learning = (
            self.load_pattern_learning()
        )


        df["Intraday Probability %"] = (
            df.apply(
                lambda row:
                self.calculate_probability(
                    row,
                    learning
                ),
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


    result = (
        IntradayProbabilityEngine()
        .run()
    )


    print("=" * 60)
    print("INTRADAY PROBABILITY COMPLETE")
    print(result)
    print("=" * 60)