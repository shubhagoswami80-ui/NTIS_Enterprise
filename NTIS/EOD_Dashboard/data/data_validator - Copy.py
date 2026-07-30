"""
NTIS EOD Dashboard Data Validator

Purpose:
    Validate availability of EOD dashboard input data.

Rules:
    - Read only
    - No data modification
    - No pipeline changes
"""

from pathlib import Path
from datetime import datetime

from EOD_Dashboard.config.dashboard_config import (
    EOD_OUTPUT_DIR,
    REQUIRED_EOD_FILES,
)

SOURCE_ROOT = Path("E:/NSE_Daily_Analysis")


def current_source_dir():
    return SOURCE_ROOT / str(datetime.today().year) / datetime.today().strftime("%B")


SOURCE_FOLDERS = [
    "01_Price_OI",
    "02_Volume_OI_Spikes",
    "03_Support_OI",
    "04_Resistance_OI",
    "05_IVR_IVP",
]

OPTIONAL_SOURCE_FOLDERS = [
    "06_Sector",
]


def check_path(path):
    return {
        "exists": path.exists(),
        "path": str(path)
    }


def validate_output_files():
    return {
        name: check_path(EOD_OUTPUT_DIR / file)
        for name, file in REQUIRED_EOD_FILES.items()
    }


def validate_source_files():
    root = current_source_dir()
    return {
        folder: check_path(root / folder)
        for folder in SOURCE_FOLDERS
    }


def validate_optional_sources():
    root = current_source_dir()
    return {
        folder: check_path(root / folder)
        for folder in OPTIONAL_SOURCE_FOLDERS
    }


def run_validation():
    print("=" * 60)
    print("NTIS EOD DATA VALIDATION")
    print("=" * 60)

    print("\nCORE OUTPUT DATA")
    for name, item in validate_output_files().items():
        print(name, "PASS" if item["exists"] else "MISSING")

    print("\nSOURCE REPORTS")
    for name, item in validate_source_files().items():
        print(name, "PASS" if item["exists"] else "MISSING")

    print("\nOPTIONAL INTELLIGENCE DATA")
    for name, item in validate_optional_sources().items():
        print(name, "AVAILABLE" if item["exists"] else "NOT AVAILABLE")


if __name__ == "__main__":
    run_validation()
