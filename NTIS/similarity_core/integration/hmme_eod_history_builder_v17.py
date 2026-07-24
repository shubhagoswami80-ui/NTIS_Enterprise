"""
HMME V1.7 EOD History Builder

Purpose:
Combine daily NTIS EOD XLS reports into historical dataset.

Adds:
- Report_Date from filename
- Historical combined dataframe

Expected folder:
E:/NSE_Daily_Analysis/2026/<Month>/01_Price_OI/
"""

from pathlib import Path
import pandas as pd
import re


class HMMEEODHistoryBuilderV17:

    def __init__(self, source_dir):
        self.source_dir = Path(source_dir)

    def build(self):

        files = list(
            self.source_dir.glob(
                "Daywise_Price_and_OI_Summary*.xlsx"
            )
        )

        frames = []

        for file in files:

            df = pd.read_excel(file)

            if "Symbol" not in df.columns:
                continue

            df["Report_Date"] = self._extract_date(
                file.name
            )

            frames.append(df)

        if not frames:
            return pd.DataFrame()

        return pd.concat(
            frames,
            ignore_index=True
        )

    def _extract_date(self, filename):

        match = re.search(
            r"(\d{4}-\d{2}-\d{2})",
            filename
        )

        if match:
            return match.group(1)

        return None
