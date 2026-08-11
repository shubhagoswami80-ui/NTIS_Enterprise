
"""
NTIS Intraday Dynamic Path Utility
Version : 2.1

Update:
- Added backward compatibility
- Existing modules using get_today_output() continue working
- Date-aware processing path supported
"""

from pathlib import Path
from intraday_execution_context import get_processing_date


BASE_DIR = Path(
    r"E:\NSE_Daily_Analysis"
)

OUTPUT_ROOT = (
    BASE_DIR
    / "Intraday"
    / "Output"
)


def get_processing_output():

    dt = get_processing_date()

    return (
        OUTPUT_ROOT
        /
        str(dt.year)
        /
        dt.strftime("%B")
        /
        dt.strftime("%Y-%m-%d")
    )


def get_today_output():

    """
    Backward compatibility wrapper.
    Existing modules continue using this.
    """

    return get_processing_output()


def get_latest_output():

    if not OUTPUT_ROOT.exists():
        return get_processing_output()

    folders = []

    for year in OUTPUT_ROOT.iterdir():

        if not year.is_dir():
            continue

        for month in year.iterdir():

            if not month.is_dir():
                continue

            for day in month.iterdir():

                if day.is_dir():
                    folders.append(day)

    if not folders:
        return get_processing_output()

    return max(
        folders,
        key=lambda x: x.name
    )
