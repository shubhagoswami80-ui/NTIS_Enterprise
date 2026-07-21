"""
HMME-13 Data Adapter
Connects existing NTIS output datasets.
"""

from pathlib import Path
import pandas as pd


class HMMEDataAdapter:

    def load_csv(self, file_path):
        path = Path(file_path)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)
