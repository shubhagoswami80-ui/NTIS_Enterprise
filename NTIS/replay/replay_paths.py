"""
=========================================================
NTIS Replay Paths
Version : 1.0
Purpose :
    Centralized path management for
    the Historical Replay Engine.
=========================================================
"""

from pathlib import Path

from replay_config import (
    BASE_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    LOG_DIR,
)


class ReplayPaths:

    BASE = Path(BASE_DIR)

    INPUT = Path(INPUT_DIR)

    OUTPUT = Path(OUTPUT_DIR)

    LOGS = Path(LOG_DIR)

    RESULTS = OUTPUT / "replay_results.csv"

    SUMMARY = OUTPUT / "replay_summary.csv"

    STATISTICS = OUTPUT / "replay_statistics.csv"

    LOG_FILE = LOGS / "historical_replay.log"

    CACHE = OUTPUT / "cache"

    REPORTS = OUTPUT / "reports"

    @classmethod
    def create(cls):

        cls.OUTPUT.mkdir(
            parents=True,
            exist_ok=True,
        )

        cls.LOGS.mkdir(
            parents=True,
            exist_ok=True,
        )

        cls.CACHE.mkdir(
            parents=True,
            exist_ok=True,
        )

        cls.REPORTS.mkdir(
            parents=True,
            exist_ok=True,
        )

    @classmethod
    def as_dict(cls):

        return {
            "BASE": cls.BASE,
            "INPUT": cls.INPUT,
            "OUTPUT": cls.OUTPUT,
            "LOGS": cls.LOGS,
            "RESULTS": cls.RESULTS,
            "SUMMARY": cls.SUMMARY,
            "STATISTICS": cls.STATISTICS,
            "LOG_FILE": cls.LOG_FILE,
            "CACHE": cls.CACHE,
            "REPORTS": cls.REPORTS,
        }