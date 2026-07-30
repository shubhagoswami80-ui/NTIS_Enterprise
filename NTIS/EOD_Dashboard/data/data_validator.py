"""
NTIS EOD Dashboard Data Validator

Production Version
"""

from pathlib import Path
from datetime import datetime

from EOD_Dashboard.config.dashboard_config import (
    EOD_OUTPUT_DIR,
    REQUIRED_EOD_FILES,
)

SOURCE_ROOT = Path("E:/NSE_Daily_Analysis")


def current_source_dir():
    today = datetime.today()
    return SOURCE_ROOT / str(today.year) / today.strftime("%B")


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


def check_path(path: Path):

    return {
        "exists": path.exists(),
        "path": str(path),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
    }


def validate_output_files():

    result = {}

    for dataset, filename in REQUIRED_EOD_FILES.items():

        full_path = EOD_OUTPUT_DIR / filename

        item = check_path(full_path)

        if item["exists"] and item["is_file"]:
            item["size_mb"] = round(
                full_path.stat().st_size / (1024 * 1024),
                2,
            )
            item["modified"] = datetime.fromtimestamp(
                full_path.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S")

        result[dataset] = item

    return result


def validate_source_files():

    base = current_source_dir()

    return {
        folder: check_path(base / folder)
        for folder in SOURCE_FOLDERS
    }


def validate_optional_sources():

    base = current_source_dir()

    return {
        folder: check_path(base / folder)
        for folder in OPTIONAL_SOURCE_FOLDERS
    }


def dashboard_health():

    outputs = validate_output_files()

    total = len(outputs)

    available = sum(
        1
        for x in outputs.values()
        if x["exists"]
    )

    return {
        "available": available,
        "missing": total - available,
        "health_percent": round(
            available * 100 / total,
            2,
        ),
    }


def run_validation():

    print("=" * 60)
    print("NTIS EOD DATA VALIDATION")
    print("=" * 60)

    health = dashboard_health()

    print(
        f"Dashboard Health : "
        f"{health['health_percent']}%"
    )

    print()

    for dataset, item in validate_output_files().items():

        status = "READY" if item["exists"] else "MISSING"

        print(f"{dataset:<25} {status}")


if __name__ == "__main__":
    run_validation()