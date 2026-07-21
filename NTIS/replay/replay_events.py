"""
=========================================================
NTIS Replay Events
Version : 1.0
Purpose :
    Event definitions for the
    Historical Replay Engine.
=========================================================
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ReplayEvent:

    timestamp: datetime
    event: str
    source: str
    payload: Any = None


class ReplayEvents:

    SESSION_STARTED = "SESSION_STARTED"

    SESSION_COMPLETED = "SESSION_COMPLETED"

    SESSION_FAILED = "SESSION_FAILED"

    TRADE_STARTED = "TRADE_STARTED"

    TRADE_COMPLETED = "TRADE_COMPLETED"

    TRADE_SKIPPED = "TRADE_SKIPPED"

    VALIDATION_STARTED = "VALIDATION_STARTED"

    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"

    EXPORT_STARTED = "EXPORT_STARTED"

    EXPORT_COMPLETED = "EXPORT_COMPLETED"

    ERROR = "ERROR"