"""
HMME Memory Manager V1.6

Purpose:
Create and maintain HMME learning memory
from replay dataset.
"""

from pathlib import Path
import pandas as pd


class HMMEMemoryManagerV16:

    def __init__(self):
        self.input_file = Path(
            "E:/NSE_Daily_Analysis/Historical_Data/HMME/hmme_replay_dataset.csv"
        )

        self.memory_dir = Path(
            "E:/NSE_Daily_Analysis/Historical_Data/HMME"
        )

        self.memory_file = (
            self.memory_dir / "hmme_memory.csv"
        )

    def build_memory(self):

        self.memory_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.input_file.exists():
            return {
                "status": "NO_DATA",
                "records": 0
            }

        df = pd.read_csv(self.input_file)

        if df.empty:
            return {
                "status": "EMPTY",
                "records": 0
            }

        memory = df.copy()

        memory.to_csv(
            self.memory_file,
            index=False
        )

        return {
            "status": "MEMORY_CREATED",
            "records": len(memory),
            "file": str(self.memory_file)
        }
