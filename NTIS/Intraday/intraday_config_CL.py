from pathlib import Path
from datetime import datetime
import configparser

CONFIG_FILE = Path(__file__).parent / "intraday_settings.ini"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

SCREENSHOT_ROOT = Path(config["PATHS"]["SCREENSHOT_ROOT"])
OUTPUT_ROOT = Path(config["PATHS"]["OUTPUT_ROOT"])
REGISTRY_ROOT = Path(config["PATHS"]["REGISTRY_ROOT"])

TODAY = datetime.today()

MONTH_FOLDER = TODAY.strftime("%B").lower() + str(TODAY.year)[-2:]
DATE_FOLDER = TODAY.strftime("%Y-%m-%d")

INPUT_FOLDER = SCREENSHOT_ROOT / MONTH_FOLDER / DATE_FOLDER
OUTPUT_FOLDER = OUTPUT_ROOT / DATE_FOLDER
REGISTRY_FILE = REGISTRY_ROOT / "intraday_file_registry.csv"


def processing_datetime():
    """Return the current processing datetime.

    Added as a hotfix: file_manager.py imports this as a callable, but
    only the static TODAY value existed. Same value, just exposed as
    a function. No logic change.
    """
    return datetime.today()


def month_folder(dt):
    """Return the month-folder name (e.g. 'july26') for a given datetime.

    Mirrors the existing MONTH_FOLDER computation, exposed as a
    callable since file_manager.py needs it parameterized by dt.
    """
    return dt.strftime("%B").lower() + str(dt.year)[-2:]


def trading_day_folder(dt):
    """Return the YYYY-MM-DD folder name for a given datetime.

    Mirrors the existing DATE_FOLDER computation, exposed as a
    callable since file_manager.py needs it parameterized by dt.
    """
    return dt.strftime("%Y-%m-%d")


def output_path():
    """Return today's output folder as a Path.

    Added as a hotfix: several modules import `output_path` from this
    module and call it as a function (output_path() / "..."), but only
    the static OUTPUT_FOLDER variable existed, causing ImportError at
    load time. This restores the missing symbol without changing any
    path values, scoring, pattern, probability, or trade logic.
    """
    return OUTPUT_FOLDER
