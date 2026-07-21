"""
=========================================================
NTIS Replay Package Archive
Version : 1.0
Purpose :
    Archive the Replay package into
    a versioned ZIP file.
=========================================================
"""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


class ReplayArchiver:

    def __init__(self, replay_folder):

        self.replay_folder = Path(replay_folder)

    def create(self, archive_name=None):

        if archive_name is None:

            archive_name = (
                self.replay_folder.parent /
                "NTIS_Replay_R1.zip"
            )

        archive_name = Path(archive_name)

        with ZipFile(
            archive_name,
            "w",
            ZIP_DEFLATED
        ) as archive:

            for file in self.replay_folder.rglob("*.py"):

                archive.write(
                    file,
                    arcname=file.relative_to(
                        self.replay_folder.parent
                    )
                )

        return archive_name

    def report(self):

        archive = self.create()

        print("=" * 60)
        print("NTIS REPLAY ARCHIVER")
        print("=" * 60)
        print(f"Archive : {archive}")
        print("=" * 60)


if __name__ == "__main__":

    ReplayArchiver(".").report()