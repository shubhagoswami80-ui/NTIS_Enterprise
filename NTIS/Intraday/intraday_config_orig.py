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
