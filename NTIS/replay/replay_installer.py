"""
=========================================================
NTIS Replay Package Installer
Version : 1.0
Purpose :
    Install and verify the Replay
    package inside NTIS.
=========================================================
"""

from pathlib import Path


class ReplayInstaller:

    def __init__(self, replay_folder):

        self.replay_folder = Path(replay_folder)

    def install(self):

        self.replay_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        print(f"Replay package installed at:\n{self.replay_folder}")

    def verify(self):

        files = list(
            self.replay_folder.glob("*.py")
        )

        print("\nVerification")
        print("-" * 40)
        print(f"Python Modules : {len(files)}")

        for file in sorted(files):
            print(file.name)

        print("-" * 40)

        return len(files)

    def run(self):

        self.install()
        self.verify()


if __name__ == "__main__":

    ReplayInstaller(".").run()