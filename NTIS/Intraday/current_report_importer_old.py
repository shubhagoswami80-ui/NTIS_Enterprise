"""
=========================================================
NTIS Intraday Current Report Importer
Version : 1.0.0
=========================================================

Purpose:
    Import manually exported Intraday Excel reports.

This module belongs ONLY to Intraday pipeline.

Output:
    E:\\NSE_Daily_Analysis\\Intraday\\Output

No EOD files are modified.
=========================================================
"""

from pathlib import Path
import logging
import pandas as pd

from intraday_config import (
    SCREENSHOT_ROOT,
    processing_datetime,
    month_folder,
    trading_day_folder,
    output_path,
    configure_logging,
)

LOGGER = logging.getLogger("NTIS_INTRADAY_IMPORTER")


REPORT_MAP = {
    "price": "PRICE_OI",
    "daywise": "PRICE_OI",
    "volume": "VOLUME_OI",
    "spike": "VOLUME_OI",
    "support": "SUPPORT_OI",
    "resistance": "RESISTANCE_OI",
    "ivr": "IVR_IVP",
    "ivp": "IVR_IVP",
    "futures": "FUTURES_OI",
}


class CurrentReportImporter:

    def __init__(self):

        configure_logging()

        self.dt = processing_datetime()

        self.input_path = self.find_input_folder()

        self.output_path = output_path()

        self.output_file = (
            self.output_path /
            "intraday_market_master.csv"
        )

        self.summary_file = (
            self.output_path /
            "intraday_import_summary.csv"
        )


    def find_input_folder(self):

        day_folder = trading_day_folder(self.dt)

        # First try configured month folder
        preferred = (
            SCREENSHOT_ROOT
            / month_folder(self.dt)
            / day_folder
            / "Intrday Files"
        )

        if preferred.exists():
            return preferred

        # Fallback: case-insensitive month folder search
        for month_dir in SCREENSHOT_ROOT.iterdir():

            if not month_dir.is_dir():
                continue

            if month_dir.name.lower() == month_folder(self.dt).lower():

                candidate = (
                    month_dir
                    / day_folder
                    / "Intrday Files"
                )

                if candidate.exists():
                    return candidate

        raise FileNotFoundError(
            f"Intraday files folder not found under: {SCREENSHOT_ROOT}"
        )


    def detect_report_type(self, filename):

        name = filename.lower()

        for key, value in REPORT_MAP.items():
            if key in name:
                return value

        return "UNKNOWN"


    def discover_files(self):

        if not self.input_path.exists():
            raise FileNotFoundError(
                f"Input folder not found: {self.input_path}"
            )

        records = []

        for file in self.input_path.iterdir():

            if (
                file.is_file()
                and file.suffix.lower() in [".xlsx", ".xls"]
                and not file.name.startswith("~$")
            ):

                records.append(
                    {
                        "File": file.name,
                        "Path": str(file),
                        "Report Type": self.detect_report_type(file.name),
                    }
                )

        return records


    def clean_columns(self, df):

        df = df.copy()

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        return df


    def find_column(self, df, names):

        cols = {
            str(c).lower(): c
            for c in df.columns
        }

        for name in names:
            if name.lower() in cols:
                return cols[name.lower()]

        return None


    def normalize(self, df, report_type):

        df = self.clean_columns(df)

        out = pd.DataFrame()

        symbol = self.find_column(
            df,
            ["Symbol", "SYMBOL", "Stock", "Ticker"]
        )

        if symbol:
            out["Symbol"] = (
                df[symbol]
                .astype(str)
                .str.upper()
                .str.strip()
            )

        mappings = {
            "CMP": ["CMP", "Close", "LTP", "Last Price"],
            "Price Chg %": ["Price Chg %", "Price Change %", "% Change"],
            "OI Chg %": ["OI Chg %", "OI Change %", "OI Change"],
            "Volume Chg %": ["Volume Chg %", "Volume Change %"],
            "IVR": ["IVR"],
            "IVP": ["IVP"],
            "PCR": ["PCR"],
            "Support": ["Support"],
            "Resistance": ["Resistance"],
        }

        for target, source_names in mappings.items():

            col = self.find_column(df, source_names)

            if col:
                out[target] = df[col]

        out["Report Type"] = report_type

        return out


    def import_reports(self):

        files = self.discover_files()

        frames = []
        summary = []

        for item in files:

            try:

                df = pd.read_excel(item["Path"])

                normalized = self.normalize(
                    df,
                    item["Report Type"]
                )

                frames.append(normalized)

                summary.append(
                    {
                        "File": item["File"],
                        "Report Type": item["Report Type"],
                        "Rows": len(normalized),
                        "Status": "SUCCESS",
                    }
                )

            except Exception as exc:

                LOGGER.exception(exc)

                summary.append(
                    {
                        "File": item["File"],
                        "Report Type": item["Report Type"],
                        "Rows": 0,
                        "Status": "FAILED",
                    }
                )

        if not frames:
            raise RuntimeError(
                "No reports imported"
            )

        master = pd.concat(
            frames,
            ignore_index=True
        )

        if "Symbol" in master.columns:
            master = (
                master
                .drop_duplicates(
                    subset=["Symbol", "Report Type"],
                    keep="last"
                )
            )

        master.to_csv(
            self.output_file,
            index=False
        )

        pd.DataFrame(summary).to_csv(
            self.summary_file,
            index=False
        )

        LOGGER.info(
            "Intraday import completed: %s",
            self.output_file
        )

        return self.output_file


if __name__ == "__main__":

    importer = CurrentReportImporter()

    print("=" * 70)
    print("NTIS INTRADAY CURRENT REPORT IMPORTER")
    print("=" * 70)

    result = importer.import_reports()

    print("Created:")
    print(result)
    print("=" * 70)
