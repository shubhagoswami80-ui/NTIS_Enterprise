"""
NTIS Intraday Dynamic Path Utility
Version 1.3

Use this utility inside Intraday modules
instead of hardcoded YYYY-MM-DD folders.
"""

from pathlib import Path
from datetime import datetime


BASE_DIR = Path(r"E:\NSE_Daily_Analysis")

OUTPUT_ROOT = (
    BASE_DIR /
    "Intraday" /
    "Output"
)


def get_today_output():

    today = datetime.today().strftime("%Y-%m-%d")

    return OUTPUT_ROOT / today


def get_latest_output():

    folders = [
        f for f in OUTPUT_ROOT.iterdir()
        if f.is_dir()
    ]

    if not folders:
        return get_today_output()

    return max(
        folders,
        key=lambda x: x.name
    )
