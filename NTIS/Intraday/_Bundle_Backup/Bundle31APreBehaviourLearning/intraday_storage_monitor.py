"""
NTIS Intraday Storage Monitor
"""

from pathlib import Path

class IntradayStorageMonitor:

    def folder_size(self, folder):

        total = 0

        for f in Path(folder).rglob("*"):
            if f.is_file():
                total += f.stat().st_size

        return round(total / (1024*1024), 2)
