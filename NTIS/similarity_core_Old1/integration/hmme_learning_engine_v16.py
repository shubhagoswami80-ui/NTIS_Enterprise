"""
HMME Learning Engine V1.6

Purpose:
Analyze HMME memory and generate learning statistics.
"""

from pathlib import Path
import pandas as pd


class HMMELearningEngineV16:

    def __init__(self):
        self.memory_file = Path(
            "E:/NSE_Daily_Analysis/Historical_Data/HMME/hmme_memory.csv"
        )

        self.output_file = Path(
            "E:/NSE_Daily_Analysis/Historical_Data/HMME/hmme_learning_summary.csv"
        )

    def learn(self):

        if not self.memory_file.exists():
            return {
                "status": "NO_MEMORY",
                "records": 0
            }

        df = pd.read_csv(self.memory_file)

        if df.empty:
            return {
                "status": "EMPTY_MEMORY",
                "records": 0
            }

        summary = pd.DataFrame()

        if "Pattern" in df.columns:
            summary = (
                df.groupby("Pattern")
                .size()
                .reset_index(name="Occurrences")
            )
        else:
            summary = pd.DataFrame({
                "Occurrences": [len(df)]
            })

        summary.to_csv(
            self.output_file,
            index=False
        )

        return {
            "status": "LEARNING_COMPLETED",
            "records": len(df),
            "file": str(self.output_file)
        }
