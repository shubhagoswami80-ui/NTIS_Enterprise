
"""
NTIS Intraday Configuration
Version: 1.0.0
"""

from pathlib import Path
from datetime import datetime
import logging

PROJECT_NAME = "NTIS Intraday"
VERSION = "1.0.0"

SCREENSHOT_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot")
PROCESSING_DATE = None

BASE_DIR = Path(r"E:\NSE_Daily_Analysis")
INTRADAY_DIR = BASE_DIR / "Intraday"
WORKING_DIR = INTRADAY_DIR / "Working"
OUTPUT_DIR = INTRADAY_DIR / "Output"
LOG_DIR = INTRADAY_DIR / "Logs"

REPORT_TYPES = [
    "Price_OI","Volume_OI","Support_OI",
    "Resistance_OI","IVR_IVP","Futures_OI","Intraday_Scan"
]

def processing_datetime():
    return datetime.strptime(PROCESSING_DATE, "%Y-%m-%d") if PROCESSING_DATE else datetime.today()

def month_folder(dt=None):
    dt = dt or processing_datetime()
    return dt.strftime("%B%y")

def trading_day_folder(dt=None):
    dt = dt or processing_datetime()
    return dt.strftime("%Y-%m-%d")

def working_path():
    dt = processing_datetime()
    p = WORKING_DIR / str(dt.year) / dt.strftime("%B") / trading_day_folder(dt)
    p.mkdir(parents=True, exist_ok=True)
    return p

def output_path():
    dt = processing_datetime()
    p = OUTPUT_DIR / str(dt.year) / dt.strftime("%B") / trading_day_folder(dt)
    p.mkdir(parents=True, exist_ok=True)
    return p

def log_path():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / "intraday.log"

def report_filename(report_name, ext="xlsx"):
    return f"{report_name}_Report_{processing_datetime().strftime('%Y-%m-%d_%H%M%S')}.{ext}"

def validate():
    if not SCREENSHOT_ROOT.exists():
        raise FileNotFoundError(f"Screenshot root not found: {SCREENSHOT_ROOT}")
    working_path()
    output_path()
    log_path()

def configure_logging():
    logging.basicConfig(
        filename=str(log_path()),
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

def show_config():
    dt = processing_datetime()
    print("="*60)
    print(PROJECT_NAME, VERSION)
    print("Screenshot Root:", SCREENSHOT_ROOT)
    print("Month Folder   :", month_folder(dt))
    print("Trading Day    :", trading_day_folder(dt))
    print("Working Folder :", working_path())
    print("Output Folder  :", output_path())
    print("Log File       :", log_path())
    print("="*60)

if __name__ == "__main__":
    configure_logging()
    validate()
    show_config()
