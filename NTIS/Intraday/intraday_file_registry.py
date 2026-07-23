"""
NTIS Intraday File Registry v1.5.4

Tracks processed files and detects:
NEW / MODIFIED / UNCHANGED
"""

from pathlib import Path
from datetime import datetime
import pandas as pd

try:
    from intraday_config import REGISTRY_FILE
except ImportError:
    REGISTRY_FILE = Path(
        r"E:\NSE_Daily_Analysis\Intraday\Database\intraday_file_registry.csv"
    )


class IntradayFileRegistry:

    def __init__(self):
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)

        if REGISTRY_FILE.exists():
            self.df = pd.read_csv(REGISTRY_FILE)
        else:
            self.df = pd.DataFrame(columns=[
                "File",
                "Path",
                "Size",
                "Modified",
                "Status",
                "Processed_Time"
            ])

    def check_file(self, file_path):

        file_path = Path(file_path)

        size = file_path.stat().st_size
        modified = datetime.fromtimestamp(
            file_path.stat().st_mtime
        ).isoformat()

        old = self.df[self.df["Path"] == str(file_path)]

        if old.empty:
            return "NEW"

        row = old.iloc[0]

        if int(row["Size"]) != size or row["Modified"] != modified:
            return "MODIFIED"

        return "UNCHANGED"


    def update(self, file_path, status="PROCESSED"):

        file_path = Path(file_path)

        self.df = self.df[
            self.df["Path"] != str(file_path)
        ]

        self.df.loc[len(self.df)] = [
            file_path.name,
            str(file_path),
            file_path.stat().st_size,
            datetime.fromtimestamp(
                file_path.stat().st_mtime
            ).isoformat(),
            status,
            datetime.now().isoformat()
        ]

        self.df.to_csv(
            REGISTRY_FILE,
            index=False
        )
