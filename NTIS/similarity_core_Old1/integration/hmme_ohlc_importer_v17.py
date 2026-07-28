"""
HMME V1.7 OHLC Importer

Purpose:
Import NSE Futures OHLC data for replay evaluation.

Expected path:
E:/NSE_Daily_Analysis/Historical_Data/OHLC/Futures/

Expected columns:
Date, Symbol, Open, High, Low, Close, Volume, OI
"""

from pathlib import Path
import pandas as pd


class HMMEOHLCImporterV17:

    def __init__(self):
        self.ohlc_dir = Path(
            "E:/NSE_Daily_Analysis/Historical_Data/OHLC/Futures"
        )

    def load(self, filename=None):

        if filename:
            file_path = self.ohlc_dir / filename
            if file_path.exists():
                return self._prepare(
                    pd.read_csv(file_path)
                )

        if not self.ohlc_dir.exists():
            return pd.DataFrame()

        files = list(self.ohlc_dir.glob("*.csv"))

        if not files:
            return pd.DataFrame()

        frames = []

        for file in files:
            frames.append(
                pd.read_csv(file)
            )

        return self._prepare(
            pd.concat(frames, ignore_index=True)
        )

    def _prepare(self, df):

        if df.empty:
            return df

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        required = [
            "Date",
            "Symbol",
            "Open",
            "High",
            "Low",
            "Close"
        ]

        available = [
            c for c in required
            if c in df.columns
        ]

        if len(available) != len(required):
            return pd.DataFrame()

        df["Symbol"] = (
            df["Symbol"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

        return df
