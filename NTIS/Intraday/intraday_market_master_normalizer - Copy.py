from datetime import datetime
"""
NTIS Intraday Market Master Normalizer
Version: 1.0

Input:
intraday_market_master_clean.csv

Output:
intraday_market_master_ntis.csv
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_market_master_clean.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_market_master_ntis.csv"
)


class IntradayMarketMasterNormalizer:

    def rename_columns(self, df):

        rename = {}

        for col in df.columns:
            c = str(col).lower().strip()

            if c.startswith("price chg"):
                rename[col] = "Price Chg %"

            elif c.startswith("oi chg %"):
                rename[col] = "OI Chg %"

            elif c.startswith("volume chg"):
                rename[col] = "Volume Chg %"

            elif c == "price":
                rename[col] = "Price"

            elif c == "oi":
                rename[col] = "OI"

            elif c == "pcr":
                rename[col] = "PCR"

            elif c == "fut oi":
                rename[col] = "Fut OI"

            elif c == "fut buildup":
                rename[col] = "Fut Buildup"

        return df.rename(columns=rename)


    def consolidate_columns(self, df):

        targets = [
            "Price Chg %",
            "OI Chg %",
            "Volume Chg %",
            "Price",
            "OI"
        ]

        for target in targets:

            cols = [
                c for c in df.columns
                if c == target
            ]

            if len(cols) > 1:
                df[target] = df[cols].bfill(axis=1).iloc[:, 0]

        return df


    def run(self):

        df = pd.read_csv(INPUT_FILE)

        df = self.rename_columns(df)

        df = self.consolidate_columns(df)

        keep = [
            c for c in [
                "Symbol",
                "Price",
                "Price Chg %",
                "OI",
                "OI Chg %",
                "PCR",
                "ATM Straddle %",
                "IV Chg",
                "IV Chg %",
                "Fut OI",
                "Fut OI Chg",
                "Fut OI Chg %",
                "Fut Buildup",
                "Volume",
                "Volume Chg %",
                "Report_Type",
                "Source_File"
            ]
            if c in df.columns
        ]

        df = df[keep]

        df = df.drop_duplicates(
            subset=["Symbol"],
            keep="last"
        )

        df.to_csv(
            OUTPUT_FILE,
            index=False
        )

        return OUTPUT_FILE


if __name__ == "__main__":

    result = IntradayMarketMasterNormalizer().run()

    print("=" * 60)
    print("INTRADAY NTIS MASTER CREATED")
    print(result)
    print("=" * 60)
