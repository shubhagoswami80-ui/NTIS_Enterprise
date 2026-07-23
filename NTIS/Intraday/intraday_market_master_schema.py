from datetime import datetime
"""
=========================================================
NTIS Intraday Final Schema Consolidator
Version : 1.0

Purpose:
    Convert intraday_market_master_ntis.csv
    into final scoring-ready schema.

Input:
    intraday_market_master_ntis.csv

Output:
    intraday_market_master_schema.csv
=========================================================
"""

from pathlib import Path
import pandas as pd


INPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_market_master_ntis.csv"
)

OUTPUT_FILE = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output\\" + datetime.today().strftime("%Y-%m-%d") + r"\intraday_market_master_schema.csv"
)


class IntradaySchemaConsolidator:

    def consolidate_metric(self, df, base_name):

        cols = [
            c for c in df.columns
            if str(c).startswith(base_name)
        ]

        if cols:
            df[base_name] = (
                df[cols]
                .bfill(axis=1)
                .iloc[:, 0]
            )

            remove = [
                c for c in cols
                if c != base_name
            ]

            df.drop(
                columns=remove,
                inplace=True,
                errors="ignore"
            )

        return df


    def clean_numeric(self, df):

        numeric_cols = [
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
            "Volume",
            "Volume Chg %"
        ]

        for col in numeric_cols:

            if col in df.columns:

                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(",", "", regex=False)
                )

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

        return df


    def run(self):

        df = pd.read_csv(INPUT_FILE)

        for col in [
            "Price Chg %",
            "OI Chg %",
            "Volume Chg %"
        ]:
            df = self.consolidate_metric(df, col)

        if "Symbol" in df.columns:

            df["Symbol"] = (
                df["Symbol"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            df = df[
                df["Symbol"].notna()
                &
                (df["Symbol"] != "NAN")
                &
                (df["Symbol"] != "")
            ]

        df = self.clean_numeric(df)

        keep = [
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

        df = df[
            [c for c in keep if c in df.columns]
        ]

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

    result = IntradaySchemaConsolidator().run()

    print("=" * 60)
    print("INTRADAY FINAL SCHEMA CREATED")
    print(result)
    print("=" * 60)
