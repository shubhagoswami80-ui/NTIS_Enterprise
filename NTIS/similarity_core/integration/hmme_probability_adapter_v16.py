"""
HMME Probability Adapter V1.6

Purpose:
Provide calibrated HMME learning output as
input for future NTIS probability enhancement.
"""

from pathlib import Path
import pandas as pd


class HMMEProbabilityAdapterV16:

    def __init__(self):
        self.calibration_file = Path(
            "E:/NSE_Daily_Analysis/Historical_Data/HMME/hmme_calibration_summary.csv"
        )

    def load_calibration(self):

        if not self.calibration_file.exists():
            return pd.DataFrame()

        return pd.read_csv(self.calibration_file)

    def get_probability_context(self):

        df = self.load_calibration()

        if df.empty:
            return {
                "status": "NO_CALIBRATION",
                "records": 0
            }

        return {
            "status": "READY",
            "records": len(df),
            "source": str(self.calibration_file)
        }
