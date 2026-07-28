"""
HMME-13 Output Manager
"""

from pathlib import Path


class HMMEOutputManager:

    def ensure_folder(self, folder):
        Path(folder).mkdir(parents=True, exist_ok=True)
