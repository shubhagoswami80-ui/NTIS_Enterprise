"""
=========================================================
NTIS Configuration
=========================================================

Purpose:
    Central configuration for NTIS.

    DO NOT hardcode values anywhere else.
    All thresholds, paths and scoring weights
    should be maintained here.

Author  : NTIS
Version : 2.0
=========================================================
"""

from pathlib import Path

# =========================================================
# ROOT FOLDERS
# =========================================================

ROOT = Path("E:/NSE_Daily_Analysis")

REPORT_ROOT = ROOT

OUTPUT = ROOT / "Output"

HISTORY = OUTPUT / "History"

DAILY_OUTPUT = OUTPUT / "Daily"

REPORT_OUTPUT = OUTPUT / "Reports"

LOG_FOLDER = ROOT / "Logs"

# =========================================================
# CURRENT REPORT LOCATION
# =========================================================

CURRENT_YEAR = "2026"

CURRENT_MONTH = "July"

DAILY_REPORTS = REPORT_ROOT / CURRENT_YEAR / CURRENT_MONTH

# =========================================================
# REPORT FOLDERS
# =========================================================

REPORT_FOLDERS = {

    "price_oi": "01_Price_OI",

    "volume_oi": "02_Volume_OI_Spikes",

    "support_oi": "03_Support_OI",

    "resistance_oi": "04_Resistance_OI",

    "ivr_ivp": "05_IVR_IVP"

}

# =========================================================
# OUTPUT FILES
# =========================================================

MASTER_FILE = OUTPUT / "market_master.csv"

RANKED_FILE = OUTPUT / "ntis_ranked_stocks.csv"

BULLISH_FILE = OUTPUT / "bullish_stocks.csv"

BEARISH_FILE = OUTPUT / "bearish_stocks.csv"

SIGNAL_HISTORY = HISTORY / "signal_history.csv"

BACKTEST_HISTORY = HISTORY / "backtest_history.csv"

# =========================================================
# SCORING WEIGHTS
# =========================================================

PRICE_WEIGHT = 25

OI_WEIGHT = 25

VOLUME_WEIGHT = 15

SUP_RES_WEIGHT = 20

IV_WEIGHT = 15

TOTAL_SCORE = 100

# =========================================================
# PRICE MOMENTUM
# =========================================================

PRICE_STRONG = 5.0

PRICE_GOOD = 3.0

PRICE_MODERATE = 2.0

PRICE_SMALL = 1.0

# =========================================================
# OI BUILDUP
# =========================================================

OI_STRONG = 10

OI_GOOD = 5

OI_SMALL = 2

# =========================================================
# VOLUME
# =========================================================

VOLUME_HUGE = 300

VOLUME_HIGH = 200

VOLUME_MEDIUM = 100

VOLUME_LOW = 50

# =========================================================
# IVR
# =========================================================

IVR_LOW = 30

IVR_MEDIUM = 50

IVR_HIGH = 70

# =========================================================
# SUPPORT / RESISTANCE DISTANCE
# =========================================================

NEAR_SUPPORT = 2.0

NEAR_RESISTANCE = 2.0

# =========================================================
# SIGNAL LEVELS
# =========================================================

STRONG_BULL = 80

BULL = 60

NEUTRAL = 40

BEAR = 20

STRONG_BEAR = 80

# =========================================================
# HISTORY SETTINGS
# =========================================================

KEEP_HISTORY_DAYS = 3650

AUTO_APPEND_HISTORY = True

REMOVE_DUPLICATE_HISTORY = True

# =========================================================
# BACKTEST SETTINGS
# =========================================================

BACKTEST_HOLDING_DAYS = 5

MIN_HISTORY_REQUIRED = 30

# =========================================================
# FUTURE FEATURES (Reserved)
# =========================================================

ENABLE_PCR_SCORE = False

ENABLE_ATM_STRADDLE_SCORE = False

ENABLE_IVHV_SCORE = False

ENABLE_AI_OPTIMIZER = False

ENABLE_SECTOR_RANKING = False

ENABLE_OPTIONS_STRATEGY = False

# =========================================================
# DISPLAY
# =========================================================

TOP_BULLISH = 20

TOP_BEARISH = 20

SHOW_DEBUG = True

SAVE_INTERMEDIATE_FILES = True

# =========================================================
# VERSION
# =========================================================

NTIS_VERSION = "2.0"