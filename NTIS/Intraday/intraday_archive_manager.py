"""
NTIS Intraday Archive Manager
Manual approval only.

No deletion.
"""

from pathlib import Path
import shutil

class IntradayArchiveManager:

    def archive(self, source, destination):

        source = Path(source)
        destination = Path(destination)

        destination.mkdir(parents=True, exist_ok=True)

        shutil.move(
            str(source),
            str(destination / source.name)
        )

        return destination
