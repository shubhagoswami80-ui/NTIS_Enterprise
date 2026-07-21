"""
=========================================================
NTIS Replay Package Information
Version : 1.0
Purpose :
    Display package information and
    installed Replay Engine modules.
=========================================================
"""

from replay_manifest import (
    PACKAGE_NAME,
    PACKAGE_VERSION,
    PACKAGE_RELEASE,
    MODULES,
)


class ReplayInfo:

    @staticmethod
    def show():

        print("=" * 60)
        print(PACKAGE_NAME)
        print("=" * 60)
        print(f"Version : {PACKAGE_VERSION}")
        print(f"Release : {PACKAGE_RELEASE}")
        print(f"Modules : {len(MODULES)}")
        print("=" * 60)

        for module in MODULES:
            print(f" - {module}")

        print("=" * 60)

    @staticmethod
    def version():

        return PACKAGE_VERSION

    @staticmethod
    def release():

        return PACKAGE_RELEASE

    @staticmethod
    def modules():

        return MODULES.copy()