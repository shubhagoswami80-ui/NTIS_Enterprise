"""
=========================================================
NTIS Utility Functions
Version : 1.0
Purpose : Common helper functions used across NTIS
=========================================================
"""

import re
from datetime import datetime
from pathlib import Path


# =========================================================
# Extract trading date from filename
# =========================================================

def extract_report_date(filename):
    """
    Extract trading date from report filename.

    Supported formats:

    1.
    Daywise_Price_and_OI_Summary_28JUL26_Report_2026-07-17.xlsx

    2.
    VolumeAndOISpikesScans_28JUL26_Report_17_7_2026.xlsx

    3.
    Support_Resistance_28JUL26_Scan_17_7_2026.xlsx

    4.
    Resistance_28JUL26_Scan_17_7_2026.xlsx

    Returns
    -------
    datetime object
    """

    filename = Path(filename).name

    # ---------------------------------------------
    # Pattern 1 : YYYY-MM-DD
    # ---------------------------------------------

    match = re.search(r"\d{4}-\d{2}-\d{2}", filename)

    if match:

        return datetime.strptime(
            match.group(),
            "%Y-%m-%d"
        )

    # ---------------------------------------------
    # Pattern 2 : DD_M_YYYY
    # ---------------------------------------------

    match = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", filename)

    if match:

        day, month, year = match.groups()

        return datetime(
            int(year),
            int(month),
            int(day)
        )

    return None


# =========================================================
# Format date
# =========================================================

def format_date(date_obj):

    if date_obj is None:
        return "Unknown"

    return date_obj.strftime("%d-%b-%Y")


# =========================================================
# Sort Excel files by trading date
# =========================================================

def sort_files_by_date(files):

    return sorted(
        files,
        key=lambda x: extract_report_date(x.name)
    )


# =========================================================
# Get latest Excel file
# =========================================================

def get_latest_file(folder):

    files = list(folder.glob("*.xlsx"))

    if len(files) == 0:

        return None

    files = sort_files_by_date(files)

    return files[-1]


# =========================================================
# Display separator
# =========================================================

def line(length=60):

    print("=" * length)


# =========================================================
# Testing
# =========================================================

if __name__ == "__main__":

    print()

    line()

    print("UTILITY TEST")

    line()

    tests = [

        "Daywise_Price_and_OI_Summary_28JUL26_Report_2026-07-17.xlsx",

        "VolumeAndOISpikesScans_28JUL26_Report_17_7_2026.xlsx",

        "Support_Resistance_28JUL26_Scan_17_7_2026.xlsx",

        "Resistance_28JUL26_Scan_17_7_2026.xlsx",

        "IVR-IVP_28JUL26_Report_2026-07-17.xlsx"

    ]

    for file in tests:

        print(file)

        print("Date :", format_date(extract_report_date(file)))

        print("-" * 60)