
import re
from pathlib import Path
import pandas as pd

from EOD_Dashboard.config.dashboard_config import NTIS_ROOT

REPORT_ROOT = NTIS_ROOT.parent


def get_available_dates():
    dates = set()

    for file in REPORT_ROOT.rglob("*"):
        if file.is_file():
            match = re.search(r"20\d{2}-\d{2}-\d{2}", file.name)
            if match:
                dates.add(match.group())

    return sorted(dates, reverse=True)


def find_file(date_name, keyword):

    for file in REPORT_ROOT.rglob("*"):
        if file.is_file():
            if date_name in file.name and keyword.lower() in file.name.lower():
                return file

    return None


def load_snapshot(date_name):

    snapshot = {}

    files = {
        "price_oi": "Price_and_OI",
        "volume_oi": "Volume",
        "support": "Support",
        "resistance": "Resistance",
        "ivr": "IVR"
    }

    for name, key in files.items():

        file = find_file(date_name, key)

        if file:
            try:
                if file.suffix.lower() in [".xlsx", ".xls"]:
                    snapshot[name] = pd.read_excel(file)
                else:
                    snapshot[name] = pd.read_csv(file)

            except Exception:
                snapshot[name] = None

    return snapshot
