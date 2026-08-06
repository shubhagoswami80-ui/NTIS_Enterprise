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

    def _validate_service_output(self, service_output):

        if service_output is None:
            return False

        if not isinstance(service_output, dict):
            return False

        if service_output.get("status") != "SERVICE_READY":
            return False

        if service_output.get("service_status") != "EVIDENCE_AVAILABLE":
            return False

        if not isinstance(service_output.get("historical_evidence"), dict):
            return False

        service_summary = service_output.get("service_summary")
        if not isinstance(service_summary, dict):
            return False

        if not service_summary.get("symbol") or not service_summary.get("date"):
            return False

        return True

    def _records_from_service_output(self, service_output):

        evidence = service_output["historical_evidence"]
        summary = service_output["service_summary"]

        market_pattern = summary.get("market_pattern")

        return [
            HistoricalEvidenceRecord(
                symbol=summary.get("symbol"),
                date=str(summary.get("date")),
                market_pattern=market_pattern,
                ntis_score=None,
                probability=None,
                entry=None,
                outcome=None,
                return_pct=evidence.get("historical_average_return"),
                accuracy=None,
                confidence=evidence.get("historical_confidence"),
            )
        ]

    def load_evidence(self, filename=None, service_output=None):

        if self._validate_service_output(service_output):
            return self._records_from_service_output(service_output)

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
