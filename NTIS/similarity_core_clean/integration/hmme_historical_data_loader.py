"""
NTIS Historical Data Loader v2.0

Bundle 02 - Historical Intelligence Layer

Loads historical CSV data and converts records
into Historical Evidence Contract objects.
"""

from pathlib import Path
import pandas as pd

from similarity_core_clean.integration.historical_evidence_contract import (
    HistoricalEvidenceRecord,
)


class HMMEHistoricalDataLoader:

    def __init__(self):
        self.history_dir = Path(
            "E:/NSE_Daily_Analysis/Database"
        )

    def load(self, filename=None):

        if not filename:
            return pd.DataFrame()

        file_path = self.history_dir / filename

        if not file_path.exists():
            return pd.DataFrame()

        return pd.read_csv(file_path)

    def load_evidence(self, filename=None):

        data = self.load(filename)

        records = []

        for _, row in data.iterrows():

            records.append(
                HistoricalEvidenceRecord(
                    symbol=row.get("symbol", ""),
                    date=str(row.get("date", "")),
                    market_pattern=row.get("market_pattern"),
                    ntis_score=row.get("ntis_score"),
                    probability=row.get("probability"),
                    entry=row.get("entry"),
                    outcome=row.get("outcome"),
                    return_pct=row.get("return_pct"),
                    accuracy=row.get("accuracy"),
                    confidence=row.get("confidence"),
                )
            )

        return records
