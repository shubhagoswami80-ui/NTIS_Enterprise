"""
NTIS Replay Dataset
"""
import pandas as pd

class ReplayDataset:
    def __init__(self, dataframe: pd.DataFrame):
        self.dataframe = dataframe

    @property
    def rows(self):
        return len(self.dataframe)
