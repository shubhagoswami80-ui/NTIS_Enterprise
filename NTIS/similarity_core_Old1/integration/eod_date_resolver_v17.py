"""
EOD Date Resolver V17

Purpose:
Detect latest available EOD report date dynamically.
No hardcoded trading dates.
"""

from pathlib import Path
import re
from datetime import datetime


class EODDateResolverV17:

    def __init__(self, base_folder):
        self.base_folder = Path(base_folder)

    def get_latest_report(self):

        files = list(
            self.base_folder.rglob("*.xlsx")
        )

        dates = []

        for file in files:
            match = re.search(
                r"(\d{4}-\d{2}-\d{2})",
                file.name
            )

            if match:
                dates.append(
                    (
                        datetime.strptime(
                            match.group(1),
                            "%Y-%m-%d"
                        ),
                        file
                    )
                )

        if not dates:
            return None

        return max(
            dates,
            key=lambda x: x[0]
        )

