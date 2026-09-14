from __future__ import annotations

from datetime import datetime
from pathlib import Path

# Fixed project locations
NSE_CODE_ROOT = Path(r"E:\NSE_Daily_Analysis\ReportGenration\ytf\NSE")
NSE_FEED_ROOT = Path(r"D:\My-data\Share_P&L\ytdata\nse_feed")


def trading_day_root(trade_date: str | None = None) -> Path:
    """Return ...\nse_feed\YYYY\Month\YYYY-MM-DD."""
    if trade_date:
        dt = datetime.strptime(trade_date, "%Y-%m-%d")
    else:
        dt = datetime.now()

    return NSE_FEED_ROOT / dt.strftime("%Y") / dt.strftime("%B") / dt.strftime("%Y-%m-%d")


def raw_root(trade_date: str | None = None) -> Path:
    return trading_day_root(trade_date)


def output_root(trade_date: str | None = None) -> Path:
    return trading_day_root(trade_date) / "output"


def ensure_day_folders(trade_date: str | None = None) -> dict[str, Path]:
    paths = {
        "raw": raw_root(trade_date),
        "output": output_root(trade_date),
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
