"""
NTIS Intraday Duplicate Detector
"""

from pathlib import Path
from collections import Counter

class IntradayDuplicateDetector:

    def scan(self, folder):

        files = [
            f.name for f in Path(folder).rglob("*")
            if f.is_file()
        ]

        duplicates = [
            item for item, count in Counter(files).items()
            if count > 1
        ]

        return duplicates
