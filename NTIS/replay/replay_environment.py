"""
=========================================================
NTIS Replay Environment
Version : 1.0
Purpose :
    Validate Replay Engine runtime
    environment and dependencies.
=========================================================
"""

import sys
import importlib


class ReplayEnvironment:

    REQUIRED_PACKAGES = [
        "pandas",
        "numpy",
    ]

    OPTIONAL_PACKAGES = [
        "openpyxl",
        "matplotlib",
    ]

    @staticmethod
    def check_package(package):

        try:
            importlib.import_module(package)
            return True
        except Exception:
            return False

    @classmethod
    def validate(cls):

        print("=" * 60)
        print("NTIS REPLAY ENVIRONMENT")
        print("=" * 60)

        print(f"Python : {sys.version.split()[0]}")
        print()

        print("Required Packages")

        for pkg in cls.REQUIRED_PACKAGES:

            status = "OK" if cls.check_package(pkg) else "MISSING"

            print(f"{pkg:<20} {status}")

        print()

        print("Optional Packages")

        for pkg in cls.OPTIONAL_PACKAGES:

            status = "OK" if cls.check_package(pkg) else "NOT INSTALLED"

            print(f"{pkg:<20} {status}")

        print("=" * 60)


if __name__ == "__main__":

    ReplayEnvironment.validate()