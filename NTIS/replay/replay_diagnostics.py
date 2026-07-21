"""
=========================================================
NTIS Replay Diagnostics
Version : 1.0
Purpose :
    Diagnostic utilities for the
    Historical Replay Engine.
=========================================================
"""

from pathlib import Path
import platform
import sys


class ReplayDiagnostics:

    @staticmethod
    def python_version():

        return sys.version.split()[0]

    @staticmethod
    def operating_system():

        return platform.platform()

    @staticmethod
    def working_directory():

        return str(Path.cwd())

    @staticmethod
    def package_status():

        return {
            "Python": ReplayDiagnostics.python_version(),
            "Operating System": ReplayDiagnostics.operating_system(),
            "Working Directory": ReplayDiagnostics.working_directory(),
        }

    @staticmethod
    def print_status():

        print("=" * 60)
        print("NTIS REPLAY DIAGNOSTICS")
        print("=" * 60)

        for key, value in ReplayDiagnostics.package_status().items():
            print(f"{key:<20}: {value}")

        print("=" * 60)


if __name__ == "__main__":
    ReplayDiagnostics.print_status()