"""
=========================================================
NTIS Replay Configuration
Version : 1.0
Purpose :
    Configuration for Historical Replay Engine
=========================================================
"""

from pathlib import Path


# =========================================================
# Paths
# =========================================================

BASE_DIR = Path("E:/NSE_Daily_Analysis")

INPUT_DIR = BASE_DIR / "Historical_Data"

OUTPUT_DIR = BASE_DIR / "Output" / "Replay"

LOG_DIR = BASE_DIR / "Logs"


# =========================================================
# Replay Settings
# =========================================================

START_DATE = None
END_DATE = None

INITIAL_CAPITAL = 100000

RISK_PER_TRADE = 0.02

BROKERAGE_PER_TRADE = 0.0

SLIPPAGE = 0.0


# =========================================================
# Output
# =========================================================

SAVE_RESULTS = True

SAVE_SUMMARY = True

PRINT_SUMMARY = True


# =========================================================
# Create Folders
# =========================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)