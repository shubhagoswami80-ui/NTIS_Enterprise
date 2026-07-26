"""
=========================================================
NTIS Intraday Probability Calibration Engine
Version : 2.2

Purpose:
    Analyse historical replay outcomes and prepare
    probability calibration feedback.

Input:
    intraday_backtest_results.csv

Output:
    intraday_probability_calibration.csv

Update:
    - Added weighted Pattern Quality Score
    - Separates Target / EOD / Stop outcomes
=========================================================
"""

from pathlib import Path
import pandas as pd



class IntradayProbabilityCalibration:


    def __init__(self, replay_file):

        self.input_file = Path(
            replay_file
        )

        self.output_file = (
            self.input_file.parent
            /
            "intraday_probability_calibration.csv"
        )



    def run(self):

        if not self.input_file.exists():

            raise FileNotFoundError(
                f"Replay file not found: {self.input_file}"
            )


        df = pd.read_csv(
            self.input_file
        )


        required_columns = [
            "Pattern",
            "Outcome",
            "Intraday Probability %",
            "Return %"
        ]


        for col in required_columns:

            if col not in df.columns:

                raise KeyError(
                    f"Missing column: {col}"
                )



        completed = df[
            df["Outcome"].isin(
                [
                    "TARGET HIT",
                    "STOP LOSS HIT",
                    "EOD EXIT"
                ]
            )
        ].copy()



        if completed.empty:

            raise ValueError(
                "No completed replay outcomes available"
            )



        calibration = (

            completed
            .groupby("Pattern")
            .agg(

                Signals=(
                    "Pattern",
                    "count"
                ),

                Target_Hits=(
                    "Outcome",
                    lambda x:
                    (x == "TARGET HIT").sum()
                ),

                Stop_Loss_Hits=(
                    "Outcome",
                    lambda x:
                    (x == "STOP LOSS HIT").sum()
                ),

                EOD_Exits=(
                    "Outcome",
                    lambda x:
                    (x == "EOD EXIT").sum()
                ),

                EOD_Positive_Exits=(
                    "Return %",
                    lambda x:
                    (x > 0).sum()
                ),

                EOD_Negative_Exits=(
                    "Return %",
                    lambda x:
                    (x <= 0).sum()
                ),

                Average_Return=(
                    "Return %",
                    "mean"
                ),

                Original_Probability=(
                    "Intraday Probability %",
                    "mean"
                )

            )

            .reset_index()

        )



        calibration["Target Success %"] = (
            calibration["Target_Hits"]
            /
            calibration["Signals"]
            *
            100
        )



        calibration["Stop Loss Rate %"] = (
            calibration["Stop_Loss_Hits"]
            /
            calibration["Signals"]
            *
            100
        )



        calibration["EOD Success %"] = (
            calibration["EOD_Positive_Exits"]
            /
            calibration["Signals"]
            *
            100
        )



        calibration["Pattern Quality Score"] = (

            (
                calibration["Target_Hits"]
                *
                1.0
            )
            +

            (
                calibration["EOD_Positive_Exits"]
                *
                0.5
            )

            -

            (
                calibration["Stop_Loss_Hits"]
                *
                1.0
            )

        )



        calibration["Pattern Quality %"] = (

            calibration["Pattern Quality Score"]
            /
            calibration["Signals"]
            *
            100

        ).round(2)



        calibration["Adjusted Probability"] = (

            calibration["Pattern Quality %"]
            .clip(
                lower=0,
                upper=100
            )

        )



        calibration["Confidence Adjustment"] = (
            calibration["Adjusted Probability"]
            .apply(
                self.get_confidence
            )
        )



        calibration.to_csv(
            self.output_file,
            index=False
        )


        return self.output_file



    def get_confidence(self, value):

        if value >= 60:

            return "IMPROVE"


        elif value >= 30:

            return "STABLE"


        return "REDUCE"



if __name__ == "__main__":

    print(
        "Use:"
    )

    print(
        "IntradayProbabilityCalibration(replay_file).run()"
    )