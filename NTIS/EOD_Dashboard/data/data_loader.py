"""
NTIS EOD Dashboard Data Loader

Purpose:
    Safe loading layer for validated EOD dashboard datasets.

Rules:
    - Read only
    - No data modification
    - No pipeline changes
"""

from datetime import datetime
import pandas as pd

from EOD_Dashboard.config.dashboard_config import (
    EOD_OUTPUT_DIR,
    REQUIRED_EOD_FILES,
)


def get_file_path(dataset_name):
    filename = REQUIRED_EOD_FILES.get(dataset_name)

    if not filename:
        return None

    return EOD_OUTPUT_DIR / filename


def load_dataset(dataset_name):
    path = get_file_path(dataset_name)

    if path is None:
        return None

    if not path.exists():
        return None

    return pd.read_csv(path)


def get_dataset_info(dataset_name):

    path = get_file_path(dataset_name)

    if path is None:
        return {
            "available": False,
            "reason": "Dataset not configured"
        }

    if not path.exists():
        return {
            "available": False,
            "path": str(path)
        }

    timestamp = datetime.fromtimestamp(
        path.stat().st_mtime
    )

    return {
        "available": True,
        "path": str(path),
        "updated": timestamp.strftime("%Y-%m-%d %H:%M:%S")
    }


def test_loader():

    print("=" * 60)
    print("NTIS EOD DATA LOADER CHECK")
    print("=" * 60)

    for name in REQUIRED_EOD_FILES:
        info = get_dataset_info(name)
        print(
            name,
            "READY" if info["available"] else "MISSING"
        )


if __name__ == "__main__":
    test_loader()
