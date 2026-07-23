"""
HMME Historical Data Loader V1.6

Purpose:
Load NTIS prediction and outcome history
from Historical_Data structure.
"""

from pathlib import Path
import pandas as pd


class HMMEHistoricalDataLoaderV16:

    def __init__(self):
        self.base_dir = Path(
            "E:/NSE_Daily_Analysis/Historical_Data"
        )

    def _load_folder(self, folder):
        files = list((self.base_dir / folder).rglob("*.csv"))
        frames = []

        for file in files:
            df = pd.read_csv(file)
            df["Source_File"] = file.name
            frames.append(df)

        if frames:
            return pd.concat(frames, ignore_index=True)

        return pd.DataFrame()

    def load_predictions(self):
        return self._load_folder("Predictions")

    def load_outcomes(self):
        return self._load_folder("Outcomes")

    def build_replay_dataset(self):

        predictions = self.load_predictions()
        outcomes = self.load_outcomes()

        if predictions.empty:
            return pd.DataFrame()

        if outcomes.empty:
            return predictions

        return predictions.merge(
            outcomes,
            on=["Symbol"],
            how="left",
            suffixes=("_PRED", "_OUT")
        )
