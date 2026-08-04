"""
===========================================================
NTIS Intraday Intelligence Loader
Version : 2.0

Purpose:
    Load historical pattern intelligence directly from the
    Pattern Intelligence Repository into in-memory caches
    for the query layer (READ-ONLY consumer).
===========================================================
"""

from pathlib import Path
import pandas as pd
from intraday_pattern_repository import IntradayPatternRepository

COMPATIBILITY_COLUMNS = (
    "Symbol",
    "Pattern",
    "Pattern_DNA",
    "Pattern_ID",
)


class IntradayIntelligenceLoader:
    """Load historical intelligence from Pattern Repository and build lookup indexes."""

    def __init__(self, learning_memory_file=None):
        self.learning_memory_file = Path(learning_memory_file) if learning_memory_file else None
        self.learning_df = pd.DataFrame()
        self.pattern_index = {}
        self.symbol_index = {}

    def load(self):
        """Load intelligence data from Pattern Repository and build indexes."""
        repo = IntradayPatternRepository()
        df = repo.repo_df.copy()

        if df.empty:
            self._clear_cache()
            return self.learning_df

        # Map repository columns to expected compatibility columns
        if "Business_Pattern_ID" in df.columns:
            df["Pattern_ID"] = df["Business_Pattern_ID"]
        if "Pattern_Name" in df.columns:
            df["Pattern"] = df["Pattern_Name"]
        if "Pattern_Fingerprint" in df.columns:
            df["Pattern_DNA"] = df["Pattern_Fingerprint"]

        self.learning_df = df
        self._ensure_compatibility_columns()
        self._build_indexes()
        return self.learning_df

    def _clear_cache(self):
        self.learning_df = pd.DataFrame()
        self.pattern_index = {}
        self.symbol_index = {}

    def _ensure_compatibility_columns(self):
        if "Pattern" not in self.learning_df.columns:
            self.learning_df["Pattern"] = ""

        if "Pattern_ID" not in self.learning_df.columns:
            self.learning_df["Pattern_ID"] = (
                self.learning_df["Pattern"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        for column in COMPATIBILITY_COLUMNS:
            if column not in self.learning_df.columns:
                self.learning_df[column] = ""

    @staticmethod
    def _clean_value(value):
        if pd.isna(value):
            return ""
        return str(value).strip()

    def _build_indexes(self):
        self.pattern_index = {}
        self.symbol_index = {}

        for idx, row in self.learning_df.iterrows():
            pattern_id = self._clean_value(row["Pattern_ID"])
            symbol = self._clean_value(row["Symbol"])

            if pattern_id:
                self.pattern_index.setdefault(pattern_id, []).append(idx)

            if symbol:
                self.symbol_index.setdefault(symbol, []).append(idx)

    def get_dataframe(self):
        return self.learning_df

    def get_pattern_index(self):
        return self.pattern_index

    def get_symbol_index(self):
        return self.symbol_index
