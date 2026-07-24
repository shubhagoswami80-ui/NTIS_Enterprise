"""
NTIS Intraday Configuration Loader v1.0

Purpose:
    Single configuration access point for all modules.

Rules:
    - No hardcoded paths inside engines
    - Read paths only from intraday_settings.ini
    - Create required folders automatically
"""

from pathlib import Path
import configparser


# ============================================================
# CONFIG FILE
# ============================================================

CONFIG_FILE = Path(__file__).parent / "intraday_settings.ini"


config = configparser.ConfigParser()


if not CONFIG_FILE.exists():
    raise FileNotFoundError(
        f"Missing configuration file: {CONFIG_FILE}"
    )


config.read(CONFIG_FILE)


# ============================================================
# PATH SETTINGS
# ============================================================

SCREENSHOT_ROOT = Path(
    config["PATHS"]["SCREENSHOT_ROOT"]
)

BASE_DIR = Path(
    config["PATHS"]["BASE_DIR"]
)

OUTPUT_ROOT = Path(
    config["PATHS"]["OUTPUT_ROOT"]
)

REGISTRY_ROOT = Path(
    config["PATHS"]["REGISTRY_ROOT"]
)

LEARNING_ROOT = Path(
    config["PATHS"]["LEARNING_ROOT"]
)

LOG_ROOT = Path(
    config["PATHS"]["LOG_ROOT"]
)


# ============================================================
# EOD SETTINGS
# ============================================================

EOD_ROOT = BASE_DIR

PRICE_OI_FOLDER = config["EOD"]["PRICE_OI_FOLDER"]

PRICE_OI_PATTERN = config["EOD"]["PRICE_OI_PATTERN"]


# ============================================================
# INTRADAY SETTINGS
# ============================================================

WORKING_FOLDER = config["INTRADAY"]["WORKING_FOLDER"]

OUTPUT_FOLDER = config["INTRADAY"]["OUTPUT_FOLDER"]

LEARNING_FOLDER = config["INTRADAY"]["LEARNING_FOLDER"]

ARCHIVE_FOLDER = config["INTRADAY"]["ARCHIVE_FOLDER"]


# ============================================================
# CREATE REQUIRED FOLDERS
# ============================================================

for folder in [
    OUTPUT_ROOT,
    REGISTRY_ROOT,
    LEARNING_ROOT,
    LOG_ROOT
]:

    folder.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# DISPLAY CONFIG
# ============================================================

def show_config():

    print("=" * 60)
    print("NTIS INTRADAY CONFIGURATION")
    print("=" * 60)

    print("BASE DIR       :", BASE_DIR)
    print("SCREENSHOT     :", SCREENSHOT_ROOT)
    print("OUTPUT         :", OUTPUT_ROOT)
    print("REGISTRY       :", REGISTRY_ROOT)
    print("LEARNING       :", LEARNING_ROOT)
    print("LOGS           :", LOG_ROOT)

    print()

    print("EOD FOLDER     :", PRICE_OI_FOLDER)
    print("EOD PATTERN    :", PRICE_OI_PATTERN)

    print("=" * 60)


if __name__ == "__main__":

    show_config()