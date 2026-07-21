"""
=========================================================
NTIS Replay Models
Version : 1.0
Purpose :
    Common data models used by the
    Historical Replay Engine
=========================================================
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# =========================================================
# Historical Market Snapshot
# =========================================================

@dataclass
class ReplayRecord:
    trade_date: datetime
    symbol: str

    ntis_score: float
    pattern: str
    probability: float
    confidence: str
    trade_bias: str

    entry_price: float
    stop_loss: float
    target: float

    actual_close: Optional[float] = None
    actual_high: Optional[float] = None
    actual_low: Optional[float] = None

    outcome: Optional[str] = None
    pnl: float = 0.0


# =========================================================
# Replay Statistics
# =========================================================

@dataclass
class ReplayStatistics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    accuracy: float = 0.0

    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0

    average_win: float = 0.0
    average_loss: float = 0.0

    max_win: float = 0.0
    max_loss: float = 0.0

    win_rate: float = 0.0
    loss_rate: float = 0.0


# =========================================================
# Replay Result
# =========================================================

@dataclass
class ReplayResult:
    symbol: str
    trade_date: datetime

    prediction: str
    actual: str

    probability: float
    confidence: str

    pnl: float

    success: bool


# =========================================================
# Similar Historical Match
# =========================================================

@dataclass
class HistoricalMatch:
    symbol: str
    trade_date: datetime

    similarity_score: float

    ntis_score: float
    pattern: str

    outcome: str

    probability: float