"""
=========================================================
NTIS Replay Logger
Version : 1.0
Purpose :
    Central logging for Historical Replay Engine
=========================================================
"""

import logging
from pathlib import Path

from replay_config import LOG_DIR


LOG_FILE = Path(LOG_DIR) / "historical_replay.log"


def get_logger(name="HistoricalReplay"):

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger