from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"E:\NSE_Daily_Analysis")

TODAY = datetime.today()
DATE_FOLDER = TODAY.strftime("%Y-%m-%d")

INTRADAY_OUTPUT = BASE_DIR / "Intraday" / "Output" / DATE_FOLDER


def get_latest_output_folder():
    root = BASE_DIR / "Intraday" / "Output"
    folders = [f for f in root.iterdir() if f.is_dir()]
    return max(folders, key=lambda x: x.name) if folders else INTRADAY_OUTPUT
