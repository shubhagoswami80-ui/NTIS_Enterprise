"""
=========================================================
NTIS Replay Loader
Version : 1.0
Purpose :
    Load Historical Replay Data
=========================================================
"""

from pathlib import Path
import pandas as pd


class ReplayLoader:

    def __init__(self):
        pass

    @staticmethod
    def load_csv(file_path):

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(file_path)

        return pd.read_csv(file_path)

    @staticmethod
    def load_excel(file_path, sheet_name=0):

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(file_path)

        return pd.read_excel(file_path, sheet_name=sheet_name)

    @staticmethod
    def load_folder(folder_path):

        folder_path = Path(folder_path)

        if not folder_path.exists():
            raise FileNotFoundError(folder_path)

        files = sorted(folder_path.glob("*.csv"))

        data = []

        for file in files:
            data.append(pd.read_csv(file))

        if not data:
            return pd.DataFrame()

        return pd.concat(data, ignore_index=True)

    @staticmethod
    def validate_columns(df, required_columns):

        missing = [
            col
            for col in required_columns
            if col not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing columns: {missing}"
            )

        return True