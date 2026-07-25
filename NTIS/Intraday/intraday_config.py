
from pathlib import Path
import configparser
from intraday_execution_context import get_processing_date

CONFIG_FILE = Path(__file__).parent / "intraday_settings.ini"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

SCREENSHOT_ROOT = Path(config["PATHS"]["SCREENSHOT_ROOT"])
OUTPUT_ROOT = Path(config["PATHS"]["OUTPUT_ROOT"])
REGISTRY_ROOT = Path(config["PATHS"]["REGISTRY_ROOT"])

TODAY = get_processing_date()

MONTH_FOLDER = TODAY.strftime("%B").lower() + str(TODAY.year)[-2:]
DATE_FOLDER = TODAY.strftime("%Y-%m-%d")

INPUT_FOLDER = SCREENSHOT_ROOT / MONTH_FOLDER / DATE_FOLDER

OUTPUT_FOLDER = (
    OUTPUT_ROOT
    / str(TODAY.year)
    / TODAY.strftime("%B")
    / DATE_FOLDER
)

REGISTRY_FILE = REGISTRY_ROOT / "intraday_file_registry.csv"

def processing_datetime():
    return get_processing_date()
