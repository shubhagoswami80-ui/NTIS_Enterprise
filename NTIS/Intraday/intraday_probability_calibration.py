"""
=========================================================
NTIS Intraday Probability Calibration Engine
Version : 3.0

Purpose:
    Analyse historical pattern intelligence from the
    Pattern Intelligence Repository and prepare probability
    calibration feedback (READ-ONLY consumer).

Input:
    intraday_pattern_repository.csv

Output:
    intraday_probability_calibration.csv
=========================================================
"""

from pathlib import Path
import pandas as pd
from intraday_pattern_repository import IntradayPatternRepository


class IntradayProbabilityCalibration:

    def __init__(self, replay_file=None):
        self.input_file = Path(replay_file) if replay_file else None
        if self.input_file:
            self.output_file = (
                self.input_file.parent
                /
                "intraday_probability_calibration.csv"
            )
        else:
            self.output_file = Path("intraday_probability_calibration.csv")

    def run(self):
        repo = IntradayPatternRepository()
        repo_df = repo.repo_df

        if repo_df.empty:
            calibration = pd.DataFrame(columns=[
                "Pattern", "Signals", "Target_Hits", "Stop_Loss_Hits",
                "EOD_Exits", "EOD_Positive_Exits", "EOD_Negative_Exits",
                "Average_Return", "Original_Probability", "Target Success %",
                "Stop Loss Rate %", "EOD Success %", "Pattern Quality Score",
                "Pattern Quality %", "Adjusted Probability", "Confidence Adjustment"
            ])
        else:
            df = repo_df.copy()
            df["Occurrences"] = pd.to_numeric(df["Occurrences"], errors="coerce").fillna(0)
            df["Successful_Trades"] = pd.to_numeric(df["Successful_Trades"], errors="coerce").fillna(0)
            df["Failed_Trades"] = pd.to_numeric(df["Failed_Trades"], errors="coerce").fillna(0)
            df["Average_PnL"] = pd.to_numeric(df["Average_PnL"], errors="coerce").fillna(0.0)

            if "Pattern_Name" not in df.columns:
                df["Pattern_Name"] = df.get("Pattern", "Neutral")

            calibration = (
                df.groupby("Pattern_Name")
                .agg(
                    Signals=("Occurrences", "sum"),
                    Target_Hits=("Successful_Trades", "sum"),
                    Stop_Loss_Hits=("Failed_Trades", "sum"),
                    Average_Return=("Average_PnL", "mean"),
                )
                .reset_index()
                .rename(columns={"Pattern_Name": "Pattern"})
            )

            calibration["EOD_Exits"] = 0
            calibration["EOD_Positive_Exits"] = calibration["Target_Hits"]
            calibration["EOD_Negative_Exits"] = calibration["Stop_Loss_Hits"]
            calibration["Original_Probability"] = 50.0

            calibration["Target Success %"] = (
                calibration["Target_Hits"]
                / calibration["Signals"].replace(0, 1)
                * 100
            )

            calibration["Stop Loss Rate %"] = (
                calibration["Stop_Loss_Hits"]
                / calibration["Signals"].replace(0, 1)
                * 100
            )

            calibration["EOD Success %"] = 0.0

            calibration["Pattern Quality Score"] = (
                calibration["Target_Hits"] * 1.0
                - calibration["Stop_Loss_Hits"] * 1.0
            )

            calibration["Pattern Quality %"] = (
                calibration["Pattern Quality Score"]
                / calibration["Signals"].replace(0, 1)
                * 100
            ).round(2)

            calibration["Adjusted Probability"] = (
                calibration["Pattern Quality %"]
                .clip(lower=0, upper=100)
            )

            calibration["Confidence Adjustment"] = (
                calibration["Adjusted Probability"]
                .apply(self.get_confidence)
            )

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        calibration.to_csv(self.output_file, index=False)
        return self.output_file

    def get_confidence(self, value):
        if value >= 60:
            return "IMPROVE"
        elif value >= 30:
            return "STABLE"
        return "REDUCE"


if __name__ == "__main__":
    print(IntradayProbabilityCalibration().run())
