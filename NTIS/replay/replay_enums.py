"""
=========================================================
NTIS Replay Enums
Version : 1.0
Purpose :
    Enumerations used throughout the
    Historical Replay Engine.
=========================================================
"""

from enum import Enum


class ReplayStatus(Enum):

    IDLE = "IDLE"
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TradeDirection(Enum):

    BUY = "BUY"
    SELL = "SELL"


class TradeOutcome(Enum):

    WIN = "WIN"
    LOSS = "LOSS"
    OPEN = "OPEN"
    SKIPPED = "SKIPPED"


class ConfidenceLevel(Enum):

    VERY_HIGH = "VERY HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"