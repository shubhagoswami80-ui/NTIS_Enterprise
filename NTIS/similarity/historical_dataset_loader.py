"""
HMME-18 Historical Dataset Loader
"""

from pathlib import Path
import pandas as pd


class HistoricalDatasetLoader:

    def load(self, file_path):
        path = Path(file_path)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)
