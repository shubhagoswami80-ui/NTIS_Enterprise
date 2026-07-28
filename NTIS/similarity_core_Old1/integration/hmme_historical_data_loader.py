from pathlib import Path
import pandas as pd


class HMMEHistoricalDataLoader:

    def __init__(self):
        self.history_dir = Path(
            "E:/NSE_Daily_Analysis/Database"
        )

    def load(self, filename=None):

        if filename:
            file_path = self.history_dir / filename

            if file_path.exists():
                return pd.read_csv(file_path)

        return pd.DataFrame()
