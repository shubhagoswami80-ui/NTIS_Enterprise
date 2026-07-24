
from pathlib import Path
from datetime import datetime
import logging

try:
    from intraday_config import SCREENSHOT_ROOT, OUTPUT_ROOT
except Exception:
    SCREENSHOT_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot")
    OUTPUT_ROOT = Path(r"E:\NSE_Daily_Analysis\Intraday\Output")

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("NTIS_INTRADAY")

class IntradayImportCore:
    def __init__(self):
        now = datetime.now()
        self.source = SCREENSHOT_ROOT / (now.strftime('%B').lower()+now.strftime('%y')) / now.strftime('%Y-%m-%d')
        self.output = OUTPUT_ROOT / now.strftime('%Y-%m-%d')
        self.output.mkdir(parents=True, exist_ok=True)

    def discover_excel_files(self):
        return [f for f in self.source.rglob('*') if f.suffix.lower() in ['.xls','.xlsx']]
