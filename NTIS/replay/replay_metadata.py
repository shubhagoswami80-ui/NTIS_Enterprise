"""
=========================================================
NTIS Replay Metadata
Version : 1.0
Purpose :
    Metadata definitions for the
    Historical Replay Engine.
=========================================================
"""


class ReplayMetadata:

    NAME = "NTIS Historical Replay Engine"

    VERSION = "1.0.0"

    RELEASE = "R1"

    AUTHOR = "NTIS"

    LICENSE = "Internal"

    STATUS = "Production"

    DESCRIPTION = (
        "Replay historical market data "
        "through the NTIS pipeline."
    )

    @classmethod
    def as_dict(cls):

        return {
            "Name": cls.NAME,
            "Version": cls.VERSION,
            "Release": cls.RELEASE,
            "Author": cls.AUTHOR,
            "License": cls.LICENSE,
            "Status": cls.STATUS,
            "Description": cls.DESCRIPTION,
        }

    @classmethod
    def print(cls):

        print("=" * 60)

        for key, value in cls.as_dict().items():
            print(f"{key:<12}: {value}")

        print("=" * 60)