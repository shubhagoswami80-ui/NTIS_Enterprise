"""
NTIS EOD Dashboard Data Loader

Read-only loading layer with filesystem freshness detection.
The loader never executes the EOD pipeline.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

from EOD_Dashboard.config.dashboard_config import (
    EOD_OUTPUT_DIR,
    REQUIRED_EOD_FILES,
)

_DATA_CACHE = {}
_CACHE_MTIME = {}


def get_file_path(dataset_name):
    filename = REQUIRED_EOD_FILES.get(dataset_name)
    if not filename:
        return None
    return Path(EOD_OUTPUT_DIR) / filename


def dataset_exists(dataset_name):
    path = get_file_path(dataset_name)
    return bool(path and path.exists())


def load_dataset(dataset_name, force_reload=False):
    path = get_file_path(dataset_name)

    if path is None or not path.exists():
        _DATA_CACHE.pop(dataset_name, None)
        _CACHE_MTIME.pop(dataset_name, None)
        return None

    mtime = path.stat().st_mtime

    if (
        not force_reload
        and dataset_name in _DATA_CACHE
        and _CACHE_MTIME.get(dataset_name) == mtime
    ):
        return _DATA_CACHE[dataset_name]

    df = pd.read_csv(path)

    _DATA_CACHE[dataset_name] = df
    _CACHE_MTIME[dataset_name] = mtime

    return df


def load_multiple(datasets, force_reload=False):
    loaded = {}
    for dataset in datasets:
        df = load_dataset(dataset, force_reload=force_reload)
        if df is not None:
            loaded[dataset] = df
    return loaded


def clear_cache():
    _DATA_CACHE.clear()
    _CACHE_MTIME.clear()


def get_dataset_info(dataset_name):
    path = get_file_path(dataset_name)

    if path is None:
        return {
            "available": False,
            "reason": "Dataset not configured",
        }

    if not path.exists():
        return {
            "available": False,
            "path": str(path),
        }

    ts = datetime.fromtimestamp(path.stat().st_mtime)

    return {
        "available": True,
        "path": str(path),
        "updated": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "cached": dataset_name in _DATA_CACHE,
    }


def test_loader():
    print("=" * 60)
    print("NTIS EOD DATA LOADER CHECK")
    print("=" * 60)

    for dataset in REQUIRED_EOD_FILES:
        info = get_dataset_info(dataset)
        status = "READY" if info["available"] else "MISSING"
        print(f"{dataset:<30} {status}")


if __name__ == "__main__":
    test_loader()
