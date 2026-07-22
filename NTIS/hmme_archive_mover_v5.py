"""
=========================================================
HMME Archive Mover v5.0

SAFE MODE

Purpose:
    Move approved HMME files into archive/quarantine.

Features:
    - Creates backup folders
    - Keeps movement log
    - No permanent deletion
    - Rollback possible

=========================================================
"""

from pathlib import Path
import pandas as pd
import shutil
from datetime import datetime


# =====================================================
# Paths
# =====================================================

BASE_DIR = Path(
    "E:/NSE_Daily_Analysis/NTIS"
)

SIMILARITY_DIR = (
    BASE_DIR /
    "similarity"
)

ARCHIVE_DIR = (
    BASE_DIR /
    "similarity_archive"
)


OUTPUT_DIR = (
    BASE_DIR /
    "Output"
)


LOG_FILE = (
    ARCHIVE_DIR /
    "archive_log.csv"
)


# Input reports

ARCHIVE_LIST = (
    OUTPUT_DIR /
    "hmme_archive_list.csv"
)


SAFE_DELETE_LIST = (
    OUTPUT_DIR /
    "hmme_dependency_safe_delete.csv"
)


# =====================================================
# Create folders
# =====================================================

def create_folders():

    folders = [

        ARCHIVE_DIR /
        "generated_modules",

        ARCHIVE_DIR /
        "safe_delete_quarantine",

        ARCHIVE_DIR /
        "release_notes"

    ]

    for folder in folders:

        folder.mkdir(
            parents=True,
            exist_ok=True
        )



# =====================================================
# Move file
# =====================================================

def move_file(
        filename,
        destination):


    source = (
        SIMILARITY_DIR /
        filename
    )


    if not source.exists():

        return None


    target = (
        destination /
        filename
    )


    shutil.move(
        str(source),
        str(target)
    )


    return {

        "File":
        filename,

        "From":
        str(source),

        "To":
        str(target),

        "Time":
        datetime.now()
        .strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    }



# =====================================================
# Process CSV
# =====================================================

def process_list(
        csv_file,
        destination,
        log):


    if not csv_file.exists():

        return


    df = pd.read_csv(
        csv_file
    )


    for _, row in df.iterrows():

        result = move_file(
            row["File"],
            destination
        )

        if result:

            log.append(
                result
            )



# =====================================================
# Main
# =====================================================

def main():

    print("="*60)
    print(
        "HMME ARCHIVE MOVER v5"
    )
    print("="*60)


    create_folders()


    log = []


    # archive files

    process_list(

        ARCHIVE_LIST,

        ARCHIVE_DIR /
        "generated_modules",

        log

    )


    # quarantine safe delete

    process_list(

        SAFE_DELETE_LIST,

        ARCHIVE_DIR /
        "safe_delete_quarantine",

        log

    )


    if log:

        pd.DataFrame(log).to_csv(
            LOG_FILE,
            index=False
        )


    print()

    print(
        "Moved:",
        len(log),
        "files"
    )

    print(
        "Log:",
        LOG_FILE
    )


if __name__ == "__main__":

    main()