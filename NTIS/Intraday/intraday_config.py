from pathlib import Path
from datetime import datetime
import configparser


# =========================================================
# NTIS Intraday Active Configuration
# Version : 2.0
#
# Purpose:
#   Active configuration module for Intraday pipeline.
#
# Update:
#   - Restored missing intraday_config.py
#   - Uses dynamic YYYY/Month/Date output structure
#   - Keeps compatibility with existing modules
# =========================================================


CONFIG_FILE = Path(__file__).parent / "intraday_settings.ini"


config = configparser.ConfigParser()

config.read(CONFIG_FILE)


SCREENSHOT_ROOT = Path(
    config["PATHS"]["SCREENSHOT_ROOT"]
)


OUTPUT_ROOT = Path(
    config["PATHS"]["OUTPUT_ROOT"]
)


REGISTRY_ROOT = Path(
    config["PATHS"]["REGISTRY_ROOT"]
)


TODAY = datetime.today()



# =========================================================
# Input folder
#
# Example:
# Screenshot
#    |
#    +-- july26
#          |
#          +-- 2026-07-25
# =========================================================

MONTH_FOLDER = (
    TODAY.strftime("%B").lower()
    +
    str(TODAY.year)[-2:]
)


DATE_FOLDER = TODAY.strftime(
    "%Y-%m-%d"
)


INPUT_FOLDER = (
    SCREENSHOT_ROOT
    /
    MONTH_FOLDER
    /
    DATE_FOLDER
)



# =========================================================
# Output folder
#
# New NTIS rule:
#
# Output
#    |
#    +-- YYYY
#          |
#          +-- Month
#                 |
#                 +-- YYYY-MM-DD
#
# =========================================================


OUTPUT_FOLDER = (
    OUTPUT_ROOT
    /
    str(TODAY.year)
    /
    TODAY.strftime("%B")
    /
    DATE_FOLDER
)



REGISTRY_FILE = (
    REGISTRY_ROOT
    /
    "intraday_file_registry.csv"
)



def processing_datetime():

    return datetime.today()



def month_folder(dt):

    return (
        dt.strftime("%B").lower()
        +
        str(dt.year)[-2:]
    )



def trading_day_folder(dt):

    return dt.strftime(
        "%Y-%m-%d"
    )



def output_path():

    return (
        OUTPUT_ROOT
        /
        str(datetime.today().year)
        /
        datetime.today().strftime("%B")
        /
        datetime.today().strftime("%Y-%m-%d")
    )