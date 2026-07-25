"""
NTIS Intraday Latest Snapshot Resolver
Version: 2.1

Supports:
- LIVE
- PROCESSING_REQUIRED
- FALLBACK
- NO_DATA

Update:
- Supports Output/YYYY/Month/YYYY-MM-DD structure
- Selects latest available snapshot <= requested date
"""

from pathlib import Path
from datetime import datetime


class IntradayLatestSnapshotResolver:

    def __init__(self, source_root, output_root):
        self.source_root = Path(source_root)
        self.output_root = Path(output_root)

    def get_available_snapshots(self):

        snapshots = []

        if not self.output_root.exists():
            return snapshots

        for year in self.output_root.iterdir():

            if not year.is_dir():
                continue

            for month in year.iterdir():

                if not month.is_dir():
                    continue

                for day in month.iterdir():

                    if day.is_dir():

                        try:
                            datetime.strptime(
                                day.name,
                                "%Y-%m-%d"
                            )
                            snapshots.append(day.name)

                        except ValueError:
                            continue

        return snapshots


    def resolve(self, requested_date):

        req = datetime.strptime(
            requested_date,
            "%Y-%m-%d"
        )

        source = self.source_root / requested_date

        output = (
            self.output_root
            / req.strftime("%Y")
            / req.strftime("%B")
            / requested_date
        )

        if source.exists():

            if output.exists():

                return {
                    "status": "LIVE",
                    "snapshot_date": requested_date,
                    "reason": "Source and intelligence snapshot available"
                }

            return {
                "status": "PROCESSING_REQUIRED",
                "snapshot_date": None,
                "reason": (
                    f"Source available for {requested_date} "
                    "but intelligence snapshot not generated"
                )
            }


        available = self.get_available_snapshots()

        valid = [
            d for d in available
            if d <= requested_date
        ]

        if valid:

            latest = sorted(
                valid,
                reverse=True
            )[0]

            return {
                "status": "FALLBACK",
                "snapshot_date": latest,
                "reason": (
                    "No source data available for requested date. "
                    "Showing latest available snapshot."
                )
            }


        return {
            "status": "NO_DATA",
            "snapshot_date": None,
            "reason": "No valid snapshot available"
        }
