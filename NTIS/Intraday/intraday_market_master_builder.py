"""
NTIS Intraday Market Master Builder
Version 1.0
"""

from pathlib import Path
from datetime import datetime
import pandas as pd

try:
    from intraday_config import SCREENSHOT_ROOT, OUTPUT_ROOT
except Exception:
    SCREENSHOT_ROOT = Path(r"D:\\My-data\\Share_P&L\\Ichart Data\\Screenshot")
    OUTPUT_ROOT = Path(r"E:\\NSE_Daily_Analysis\\Intraday\\Output")


class IntradayMarketMasterBuilder:

    def __init__(self):
        now = datetime.now()
        self.source = SCREENSHOT_ROOT / (now.strftime("%B").lower()+now.strftime("%y")) / now.strftime("%Y-%m-%d")
        self.output = OUTPUT_ROOT / now.strftime("%Y-%m-%d")
        self.output.mkdir(parents=True, exist_ok=True)

    def report_type(self, name):
        n = name.lower()
        rules = {
            "PRICE_OI": ["price","daywise"],
            "FUTURES_OI": ["futures"],
            "VOLUME_OI": ["volume","spike"],
            "IVR_IVP": ["ivr","ivp"],
            "SUPPORT": ["support"],
            "RESISTANCE": ["resistance"]
        }
        for k,v in rules.items():
            if any(x in n for x in v):
                return k
        return "UNKNOWN"

    def build(self):
        frames = []

        for file in self.source.rglob("*"):
            if file.suffix.lower() not in [".xls",".xlsx"]:
                continue

            df = pd.read_excel(file)
            df.columns = [str(c).strip() for c in df.columns]

            symbol = None
            for c in df.columns:
                if c.lower() in ["symbol","stock","ticker"]:
                    symbol = c
                    break

            if symbol:
                df["Symbol"] = df[symbol].astype(str).str.upper().str.strip()

            df["Report_Type"] = self.report_type(file.name)
            df["Source_File"] = file.name

            frames.append(df)

        if not frames:
            raise RuntimeError("No reports found")

        master = pd.concat(frames, ignore_index=True)

        output = self.output / "intraday_market_master_latest.csv"
        master.to_csv(output, index=False)

        return output


if __name__ == "__main__":
    result = IntradayMarketMasterBuilder().build()
    print("Created:", result)
