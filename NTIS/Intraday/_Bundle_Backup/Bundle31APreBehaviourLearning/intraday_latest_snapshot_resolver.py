"""
NTIS Intraday Latest Snapshot Resolver
Version: 2.2

Purpose:
    Decide dashboard snapshot status.

States:
    LIVE
    PROCESSING_REQUIRED
    FALLBACK
    NO_DATA

Update:
    - Supports Output/YYYY/Month/YYYY-MM-DD structure
    - Validates completed intelligence snapshot
    - Ignores incomplete snapshot folders
    - Selects latest valid snapshot <= requested date
"""

from pathlib import Path
from datetime import datetime


class IntradayLatestSnapshotResolver:

    REQUIRED_FILES = [
        "intraday_trade_candidates.csv",
        "intraday_probability_analysis.csv",
        "intraday_signal_evolution.csv"
    ]


    def __init__(self, source_root, output_root):

        self.source_root = Path(source_root)
        self.output_root = Path(output_root)


    def is_valid_snapshot(self, snapshot_path):

        if not snapshot_path.exists():
            return False

        for file in self.REQUIRED_FILES:

            if not (
                snapshot_path / file
            ).exists():

                return False

        return True


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

                    if not day.is_dir():
                        continue


                    try:

                        datetime.strptime(
                            day.name,
                            "%Y-%m-%d"
                        )


                        if self.is_valid_snapshot(day):

                            snapshots.append(
                                day.name
                            )

                    except ValueError:

                        continue


        return snapshots


    def get_snapshot_path(self, snapshot_date):

        dt = datetime.strptime(
            snapshot_date,
            "%Y-%m-%d"
        )

        return (
            self.output_root
            /
            dt.strftime("%Y")
            /
            dt.strftime("%B")
            /
            snapshot_date
        )


    def resolve(self, requested_date):

        source = (
            self.source_root
            /
            requested_date
        )


        requested_snapshot = (
            self.get_snapshot_path(
                requested_date
            )
        )


        if source.exists():

            if self.is_valid_snapshot(
                requested_snapshot
            ):

                return {
                    "status": "LIVE",
                    "snapshot_date": requested_date,
                    "reason": (
                        "Source and intelligence "
                        "snapshot available"
                    )
                }


            return {
                "status": "PROCESSING_REQUIRED",
                "snapshot_date": None,
                "reason": (
                    f"Source available for {requested_date} "
                    "but intelligence snapshot is incomplete"
                )
            }


        available = (
            self.get_available_snapshots()
        )


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
                    "Showing latest valid snapshot."
                )
            }


        return {
            "status": "NO_DATA",
            "snapshot_date": None,
            "reason": (
                "No valid snapshot available"
            )
        }