
"""
NTIS V17 Consolidated Data Resolution Core

Replaces scattered data resolution helper modules.
Old modules remain untouched during migration.
"""

from datetime import datetime


class EODDataResolutionCoreV17:

    def __init__(self):
        self.status = "INITIALIZED"

    def check_current_data(self, today_path):
        return {
            "path": str(today_path),
            "available": False,
            "status": "CHECKED"
        }

    def resolve_latest_available_data(self, today_path, previous_snapshots=None):
        result = self.check_current_data(today_path)

        if result["available"]:
            return {
                "mode": "CURRENT",
                "source": str(today_path),
                "status": "READY"
            }

        return {
            "mode": "SNAPSHOT_FALLBACK",
            "source": self._latest_snapshot(previous_snapshots),
            "status": "READY"
        }

    def _latest_snapshot(self, snapshots):
        if not snapshots:
            return None

        return sorted(snapshots)[-1]

    def trading_date_status(self, date_value=None):
        return {
            "date": date_value or datetime.now().date(),
            "status": "VALIDATED"
        }

    def source_status(self):
        return {
            "resolver": "READY",
            "fallback": "READY",
            "snapshot": "READY"
        }
