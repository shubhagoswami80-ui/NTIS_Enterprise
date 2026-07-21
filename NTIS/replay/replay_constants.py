"""
=========================================================
NTIS Replay Constants
Version : 1.0
Purpose :
    Shared constants used by the
    Historical Replay Engine
=========================================================
"""

# =========================================================
# Trade Outcomes
# =========================================================

WIN = "WIN"
LOSS = "LOSS"
OPEN = "OPEN"
SKIPPED = "SKIPPED"


# =========================================================
# Trade Direction
# =========================================================

BUY = "BUY"
SELL = "SELL"


# =========================================================
# Confidence Levels
# =========================================================

VERY_HIGH = "VERY HIGH"
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"


# =========================================================
# Output Files
# =========================================================

REPLAY_RESULTS_FILE = "replay_results.csv"

REPLAY_SUMMARY_FILE = "replay_summary.csv"

REPLAY_STATISTICS_FILE = "replay_statistics.csv"

REPLAY_LOG_FILE = "historical_replay.log"


# =========================================================
# Column Names
# =========================================================

SYMBOL = "Symbol"
DATE = "Trade Date"

ENTRY = "Entry"
STOPLOSS = "Stop Loss"
TARGET = "Target"

PROBABILITY = "Probability"

PNL = "PnL"

SUCCESS = "success"

OUTCOME = "Outcome"