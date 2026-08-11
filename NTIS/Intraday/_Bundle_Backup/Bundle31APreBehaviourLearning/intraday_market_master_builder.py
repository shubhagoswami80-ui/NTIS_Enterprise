"""
NTIS Intraday Market Master Builder
Version 1.2

Update:
- Uses centralized processing date context
- Supports missed day / replay execution
- No change to build logic
"""

from pathlib import Path
import pandas as pd

from intraday_config import SCREENSHOT_ROOT
from intraday_execution_context import get_processing_date
from intraday_path_config import get_processing_output


class IntradayMarketMasterBuilder:

    def __init__(self):

        dt = get_processing_date()

        self.source = (
            SCREENSHOT_ROOT
            /
            (
                dt.strftime("%B").lower()
                +
                dt.strftime("%y")
            )
            /
            dt.strftime("%Y-%m-%d")
        )

        self.output = get_processing_output()

        self.output.mkdir(
            parents=True,
            exist_ok=True
        )


    def report_type(self, name):

        n = name.lower()

        rules = {
            "PRICE_OI": ["price", "daywise"],
            "FUTURES_OI": ["futures"],
            "VOLUME_OI": ["volume", "spike"],
            "IVR_IVP": ["ivr", "ivp"],
            "SUPPORT": ["support"],
            "RESISTANCE": ["resistance"]
        }

        for k, v in rules.items():

            if any(x in n for x in v):
                return k

        return "UNKNOWN"


    def build(self):

        frames = []

        for file in self.source.rglob("*"):

            if file.suffix.lower() not in [".xls", ".xlsx"]:
                continue

            df = pd.read_excel(file)

            df.columns = [
                str(c).strip()
                for c in df.columns
            ]

            symbol = None

            for c in df.columns:

                if c.lower() in [
                    "symbol",
                    "stock",
                    "ticker"
                ]:
                    symbol = c
                    break

            if symbol:

                df["Symbol"] = (
                    df[symbol]
                    .astype(str)
                    .str.upper()
                    .str.strip()
                )

            df["Report_Type"] = self.report_type(file.name)
            df["Source_File"] = file.name

            frames.append(df)

        if not frames:

            raise RuntimeError(
                f"No reports found in {self.source}"
            )

        master = pd.concat(
            frames,
            ignore_index=True
        )

        output = (
            self.output
            /
            "intraday_market_master_latest.csv"
        )

        master.to_csv(
            output,
            index=False
        )

        return output


if __name__ == "__main__":

    result = (
        IntradayMarketMasterBuilder()
        .build()
    )

    print(
        "Created:",
        result
    )
