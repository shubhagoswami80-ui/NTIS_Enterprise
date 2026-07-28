from pathlib import Path
import pandas as pd


class NTISDataBridge:

    def __init__(self):

        self.output_dir = Path(
            "E:/NSE_Daily_Analysis/Output"
        )


    def load_data(self):

        files = {
            "market": "market_master.csv",
            "probability": "ntis_probability_analysis.csv",
            "pattern": "ntis_pattern_analysis.csv",
            "outcome": "ntis_outcome_report.csv"
        }

        data = {}

        for key, file in files.items():

            path = self.output_dir / file

            if path.exists():
                data[key] = pd.read_csv(path)
            else:
                data[key] = None

        return data