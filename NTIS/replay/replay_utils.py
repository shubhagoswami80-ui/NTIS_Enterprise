"""
=========================================================
NTIS Replay Utilities
Version : 1.0
Purpose :
    Common utility functions used by
    Historical Replay Engine
=========================================================
"""

from pathlib import Path
from datetime import datetime


def ensure_directory(path):

    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    return path


def file_exists(file_path):

    return Path(file_path).exists()


def timestamp():

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def trading_day(date):

    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")

    return date.strftime("%A") not in ("Saturday", "Sunday")


def percentage(part, whole):

    if whole == 0:
        return 0.0

    return round((part / whole) * 100, 2)


def safe_float(value, default=0.0):

    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):

    try:
        return int(value)
    except Exception:
        return default