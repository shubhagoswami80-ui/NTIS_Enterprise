
from pathlib import Path
import configparser
from intraday_execution_context import get_processing_date

CONFIG_FILE = Path(__file__).parent / "intraday_settings.ini"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

SCREENSHOT_ROOT = Path(config["PATHS"]["SCREENSHOT_ROOT"])
HISTORICAL_ROOT = Path(config["PATHS"]["HISTORICAL_ROOT"])
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


# =========================================================
# BEHAVIOUR NORMALIZATION THRESHOLDS & BANDS
# =========================================================

PRICE_BEHAVIOUR_BANDS = {
    "STRONG_UP": 2.0,
    "UP": 0.5,
    "DOWN": -0.5,
    "STRONG_DOWN": -2.0,
}

OI_BEHAVIOUR_BANDS = {
    "STRONG_ACCUMULATION": 1.5,
    "STRONG_LIQUIDATION": -1.5,
}

VOLUME_BEHAVIOUR_BANDS = {
    "SURGE": 100.0,
    "EXPANSION": 50.0,
    "CONTRACTION": -50.0,
}

PCR_BEHAVIOUR_BANDS = {
    "BULLISH_SUPPORT": 1.3,
    "BEARISH_RESISTANCE": 0.7,
}

IV_BEHAVIOUR_BANDS = {
    "HIGH_REGIME": 80.0,
    "LOW_REGIME": 20.0,
}

SCORE_BEHAVIOUR_BANDS = {
    "STRONG_BULLISH": 75.0,
    "MODERATE_BULLISH": 60.0,
    "MODERATE_BEARISH": 40.0,
    "STRONG_BEARISH": 25.0,
}

NORMALIZATION_VERSION = "1.0"
PDNA_VERSION = "1.0"

PDNA_FIELD_ORDER = (
    "NORMALIZATION",
    "PDNA",
    "PRICE",
    "OI",
    "VOLUME",
    "PCR",
    "IV",
    "SCORE",
    "PATTERN",
    "DIRECTION",
)

ADMISSION_POLICY_CONFIG = {
    "MIN_SCORE": 25.0,
    "REQUIRE_VALIDATION_SIGNAL": False,
}
