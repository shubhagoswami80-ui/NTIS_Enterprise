
"""
NTIS Intraday Latest Snapshot Resolver
Version: 2.0

Purpose:
    Decide dashboard snapshot status.

States:
    LIVE
    PROCESSING_REQUIRED
    FALLBACK
    NO_DATA
"""

from pathlib import Path


class IntradayLatestSnapshotResolver:

    def __init__(self, source_root, output_root):

        self.source_root = Path(source_root)
        self.output_root = Path(output_root)


    def resolve(self, requested_date):

        source = self.source_root / requested_date
        output = self.output_root / requested_date

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


        available = [
            x for x in self.output_root.iterdir()
            if x.is_dir()
        ]

        if available:

            latest = sorted(
                available,
                key=lambda x: x.name,
                reverse=True
            )[0]

            return {
                "status": "FALLBACK",
                "snapshot_date": latest.name,
                "reason": "No source data available for requested date"
            }


        return {
            "status": "NO_DATA",
            "snapshot_date": None,
            "reason": "No valid snapshot available"
        }
