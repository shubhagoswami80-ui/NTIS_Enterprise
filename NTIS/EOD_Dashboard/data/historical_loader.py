"""
NTIS Historical Loader
Production Version
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from EOD_Dashboard.config.dashboard_config import NTIS_ROOT

REPORT_ROOT = NTIS_ROOT.parent

_DATE_PATTERN = re.compile(r"20\d{2}-\d{2}-\d{2}")

_CACHE = {}


def get_available_dates():

    dates = set()

    for file in REPORT_ROOT.rglob("*"):

        if not file.is_file():
            continue

        match = _DATE_PATTERN.search(file.name)

        if match:
            dates.add(match.group())

    return sorted(dates, reverse=True)


def find_file(date_name, keyword):

    keyword = keyword.lower()

    for file in REPORT_ROOT.rglob("*"):

        if (
            file.is_file()
            and date_name in file.name
            and keyword in file.name.lower()
        ):
            return file

    return None


def _load_file(path):

    if path is None:
        return None

    key = str(path)

    if key in _CACHE:
        return _CACHE[key]

    try:

        if path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)

        _CACHE[key] = df
        return df

    except Exception:
        return None


def load_snapshot(date_name, force_reload=False):

    if force_reload:
        clear_cache()

    datasets = {
        "price_oi": "Price_and_OI",
        "volume_oi": "Volume",
        "support": "Support",
        "resistance": "Resistance",
        "ivr": "IVR",
    }

    snapshot = {}

    for name, keyword in datasets.items():

        snapshot[name] = _load_file(
            find_file(date_name, keyword)
        )

    return snapshot


def clear_cache():
    _CACHE.clear()


def snapshot_available(date_name):

    return any(
        find_file(date_name, keyword)
        for keyword in (
            "Price_and_OI",
            "Volume",
            "Support",
            "Resistance",
            "IVR",
        )
    )