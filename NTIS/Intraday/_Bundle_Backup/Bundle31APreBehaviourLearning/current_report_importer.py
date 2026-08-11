"""
NTIS Intraday Current Report Importer v1.5.4

Adds registry based file tracking.
"""

from intraday_config import INPUT_FOLDER
from intraday_file_registry import IntradayFileRegistry


def discover_files():

    if not INPUT_FOLDER.exists():
        print("Report folder not found:")
        print(INPUT_FOLDER)
        return []

    return list(INPUT_FOLDER.glob("*.xlsx"))


def filter_files():

    registry = IntradayFileRegistry()

    files = discover_files()

    process_files = []

    print("=" * 70)
    print("NTIS INTRADAY FILE REGISTRY CHECK")
    print("=" * 70)

    for file in files:

        status = registry.check_file(file)

        print(status, ":", file.name)

        if status in ["NEW", "MODIFIED"]:
            process_files.append(file)
            registry.update(file)

    print("-" * 70)
    print("Total files:", len(files))
    print("Processing required:", len(process_files))

    return process_files


if __name__ == "__main__":
    filter_files()
