"""
NTIS EOD Dashboard Configuration

Read only configuration layer.
"""

from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------
# Project Paths
# ---------------------------------------------------------

NTIS_ROOT = Path(__file__).resolve().parents[2]

BASE_DIR = NTIS_ROOT.parent

OUTPUT_DIR = BASE_DIR / "Output"
DATABASE_DIR = BASE_DIR / "Database"
LOG_DIR = BASE_DIR / "Logs"

TODAY = datetime.today()
YEAR = str(TODAY.year)
MONTH = TODAY.strftime("%B")

CURRENT_REPORT_DIR = BASE_DIR / YEAR / MONTH

EOD_OUTPUT_DIR = OUTPUT_DIR


# ---------------------------------------------------------
# Dashboard Files
# ---------------------------------------------------------

REQUIRED_EOD_FILES = {
    "market_master": "market_master.csv",
    "ranking": "ntis_ranked_stocks.csv",
    "probability": "ntis_probability_analysis.csv",
    "long_probability": "ntis_long_probability.csv",
    "short_probability": "ntis_short_probability.csv",
    "patterns": "ntis_pattern_analysis.csv",
    "trade_candidates": "ntis_trade_candidates.csv",
    "outcome": "ntis_outcome_report.csv",
}


# ---------------------------------------------------------
# Dashboard Settings
# ---------------------------------------------------------

APP_TITLE = "NTIS EOD Dashboard"

DEFAULT_PAGE = "Market Overview"

TABLE_PAGE_SIZE = 25

CACHE_ENABLED = True


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_output_file(key: str) -> Path:
    """
    Return absolute path of a configured NTIS output file.
    """
    return EOD_OUTPUT_DIR / REQUIRED_EOD_FILES[key]


def output_exists(key: str) -> bool:
    """
    Check whether a configured output exists.
    """
    return get_output_file(key).exists()


def list_available_outputs() -> dict:
    """
    Return existence status of all configured outputs.
    """
    return {
        key: output_exists(key)
        for key in REQUIRED_EOD_FILES
    }


def show_config():

    print("=" * 60)
    print("NTIS EOD DASHBOARD CONFIG")
    print("=" * 60)
    print("NTIS Root :", NTIS_ROOT)
    print("Base      :", BASE_DIR)
    print("Output    :", EOD_OUTPUT_DIR)
    print("Database  :", DATABASE_DIR)
    print("Logs      :", LOG_DIR)
    print("=" * 60)