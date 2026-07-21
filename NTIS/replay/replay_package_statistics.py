"""
=========================================================
NTIS Replay Package Statistics
Version : 1.0
Purpose :
    Provide package-level statistics
    for the Historical Replay Engine.
=========================================================
"""

from pathlib import Path


class ReplayPackageStatistics:

    def __init__(self, replay_folder):

        self.replay_folder = Path(replay_folder)

    def python_files(self):

        return sorted(self.replay_folder.glob("*.py"))

    def total_modules(self):

        return len(self.python_files())

    def total_lines(self):

        lines = 0

        for file in self.python_files():

            with open(file, "r", encoding="utf-8") as f:
                lines += sum(1 for _ in f)

        return lines

    def largest_module(self):

        modules = []

        for file in self.python_files():

            with open(file, "r", encoding="utf-8") as f:

                modules.append(
                    (
                        file.name,
                        sum(1 for _ in f)
                    )
                )

        return max(modules, key=lambda x: x[1])

    def report(self):

        print("=" * 60)
        print("NTIS REPLAY PACKAGE STATISTICS")
        print("=" * 60)

        print(f"Modules      : {self.total_modules()}")
        print(f"Total Lines  : {self.total_lines()}")

        module, lines = self.largest_module()

        print(f"Largest File : {module}")
        print(f"Lines        : {lines}")

        print("=" * 60)


if __name__ == "__main__":

    ReplayPackageStatistics(".").report()