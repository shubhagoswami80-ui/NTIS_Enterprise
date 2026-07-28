"""
HMME-18 Bhav Copy Loader
"""

from pathlib import Path
import pandas as pd


class BhavCopyLoader:

    def load(self, file_path):
        path = Path(file_path)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)
