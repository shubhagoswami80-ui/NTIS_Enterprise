"""
NTIS Intraday Data Quality Monitor
Manual governance mode
"""

from pathlib import Path

class IntradayDataQualityMonitor:

    def check(self, folder):

        folder = Path(folder)

        return {
            "Folder Exists": folder.exists(),
            "Status": "READY" if folder.exists() else "ISSUE"
        }
