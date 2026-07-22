"""
=========================================================
NTIS Intraday Market Master Cleaner
Version : 1.0

Purpose:
    Clean intraday_market_master_latest.csv

Input:
    Intraday Market Master Raw CSV

Output:
    intraday_market_master_clean.csv

Intraday pipeline only.
=========================================================
"""

from pathlib import Path
import pandas as pd
import re


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_market_master_latest.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\2026-07-22\intraday_market_master_clean.csv"
)


class IntradayMarketMasterCleaner:

    def remove_noise_columns(self, df):

        remove = []

        for col in df.columns:

            name = str(col).lower()

            if (
                name.startswith("unnamed")
                or "exported data" in name
            ):
                remove.append(col)

        return df.drop(
            columns=remove,
            errors="ignore"
        )


    def normalize_columns(self, df):

        mapping = {}

        for col in df.columns:

            clean = (
                str(col)
                .strip()
                .lower()
                .replace("_", " ")
            )

            if clean in [
                "price chg%",
                "price chg %",
                "price chg (%)",
                "price change %",
                "price change"
            ]:
                mapping[col] = "Price Chg %"

            elif clean in [
                "oi chg%",
                "oi chg %",
                "oi chg (%)",
                "oi change %"
            ]:
                mapping[col] = "OI Chg %"

            elif clean in [
                "volume chg%",
                "volume chg (%)",
                "volume change %"
            ]:
                mapping[col] = "Volume Chg %"

            elif clean in [
                "symbol",
                "stock",
                "ticker"
            ]:
                mapping[col] = "Symbol"

        return df.rename(columns=mapping)


    def clean_symbol(self, df):

        if "Symbol" in df.columns:

            df["Symbol"] = (
                df["Symbol"]
                .astype(str)
                .str.upper()
                .str.strip()
            )

        return df


    def run(self):

        if not INPUT_FILE.exists():

            raise FileNotFoundError(
                INPUT_FILE
            )

        df = pd.read_csv(
            INPUT_FILE
        )

        df = self.remove_noise_columns(df)

        df = self.normalize_columns(df)

        df = self.clean_symbol(df)

        df = df.drop_duplicates(
            keep="last"
        )

        df.to_csv(
            OUTPUT_FILE,
            index=False
        )

        return OUTPUT_FILE


if __name__ == "__main__":

    result = IntradayMarketMasterCleaner().run()

    print("=" * 60)
    print("INTRADAY MASTER CLEAN COMPLETE")
    print(result)
    print("=" * 60)
