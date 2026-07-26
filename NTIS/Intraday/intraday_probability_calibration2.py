"""
=========================================================
NTIS Intraday Probability Calibration Engine
Version : 2.0

Purpose:
    Analyse historical replay outcomes and prepare
    probability calibration feedback.

Input:
    intraday_backtest_results.csv

Output:
    intraday_probability_calibration.csv

Rules:
    - Target Hit = Successful Signal
    - Stop Loss Hit = Failed Signal
    - EOD Exit = Completed but neutral
    - Calculates pattern performance
=========================================================
"""

from pathlib import Path
import pandas as pd



class IntradayProbabilityCalibration:


    def __init__(
        self,
        replay_file
    ):

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
                    sum(
                        x == "TARGET HIT"
                    )
                ),

                Stop_Loss_Hits=(
                    "Outcome",
                    lambda x:
                    sum(
                        x == "STOP LOSS HIT"
                    )
                ),

                EOD_Exits=(
                    "Outcome",
                    lambda x:
                    sum(
                        x == "EOD EXIT"
                    )
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


        calibration["Win Rate %"] = (
            calibration["Target_Hits"]
            /
            calibration["Signals"]
        ) * 100


        calibration["Adjusted Probability"] = (
            calibration["Win Rate %"]
        )


        calibration["Confidence Adjustment"] = (
            calibration["Win Rate %"]
            .apply(
                self.get_confidence
            )
        )


        calibration.to_csv(
            self.output_file,
            index=False
        )


        return self.output_file



    def get_confidence(
        self,
        win_rate
    ):

        if win_rate >= 70:

            return "IMPROVE"

        elif win_rate >= 40:

            return "STABLE"

        else:

            return "REDUCE"



if __name__ == "__main__":

    print(
        "Use:"
    )

    print(
        "IntradayProbabilityCalibration(replay_file).run()"
    )