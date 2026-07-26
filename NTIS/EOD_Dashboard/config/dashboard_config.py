"""
NTIS EOD Dashboard Configuration

Purpose:
    Central configuration for EOD Dashboard.

Rules:
    - No dashboard logic here
    - No data processing here
    - Single source for paths/settings
"""

from pathlib import Path
from datetime import datetime


# NTIS Root
NTIS_ROOT = Path("E:/NSE_Daily_Analysis/NTIS")

# EOD Dashboard Root
DASHBOARD_ROOT = NTIS_ROOT / "EOD_Dashboard"

# EOD Output Data
EOD_OUTPUT_DIR = Path("E:/NSE_Daily_Analysis/Output")

# Replay Data Source
REPLAY_OUTPUT_DIR = EOD_OUTPUT_DIR


# Dashboard folders
APP_DIR = DASHBOARD_ROOT / "app"
DATA_DIR = DASHBOARD_ROOT / "data"
PAGES_DIR = DASHBOARD_ROOT / "pages"
REPLAY_DIR = DASHBOARD_ROOT / "replay"
COMPONENTS_DIR = DASHBOARD_ROOT / "components"
LOG_DIR = DASHBOARD_ROOT / "logs"


# Required EOD files
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


# Dashboard metadata
DASHBOARD_NAME = "NTIS EOD Intelligence Dashboard"
VERSION = "v1.0"


def show_config():

    print("=" * 60)
    print(DASHBOARD_NAME)
    print("=" * 60)

    print("Version:", VERSION)
    print("Output:", EOD_OUTPUT_DIR)

    print("\nRequired Files:")
    for key, value in REQUIRED_EOD_FILES.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    show_config()