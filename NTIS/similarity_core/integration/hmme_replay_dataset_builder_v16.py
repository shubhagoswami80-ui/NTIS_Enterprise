"""
HMME Replay Dataset Builder V1.6

Builds replay dataset from HMME historical loader.
"""

from pathlib import Path
import pandas as pd

from similarity_core.integration.hmme_historical_data_loader_v16 import (
    HMMEHistoricalDataLoaderV16
)


class HMMEReplayDatasetBuilderV16:

    def __init__(self):
        self.output_dir = Path(
            "E:/NSE_Daily_Analysis/Historical_Data/HMME"
        )
        self.output_file = (
            self.output_dir / "hmme_replay_dataset.csv"
        )

    def build(self):

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        loader = HMMEHistoricalDataLoaderV16()

        dataset = loader.build_replay_dataset()

        if dataset.empty:
            return {
                "status": "EMPTY",
                "records": 0
            }

        dataset.to_csv(
            self.output_file,
            index=False
        )

        return {
            "status": "CREATED",
            "records": len(dataset),
            "file": str(self.output_file)
        }
