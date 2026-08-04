"""
===========================================================
NTIS Intraday Intelligence Loader

Purpose:
    Load historical pattern statistics into the in-memory
    intelligence cache used by the query layer.

Input:
    pattern_statistics.csv

Compatibility:
    Supports the existing learning-memory input contract when
    an explicit source file is supplied.
===========================================================
"""

from pathlib import Path

import pandas as pd

COMPATIBILITY_COLUMNS = (
    "Symbol",
    "Pattern",
    "Pattern_DNA",
    "Pattern_ID",
)


class IntradayIntelligenceLoader:
    """Load historical intelligence and build lookup indexes."""

    def __init__(self, learning_memory_file):
        self.learning_memory_file = Path(learning_memory_file)

        self.learning_df = pd.DataFrame()

        self.pattern_index = {}

        self.symbol_index = {}

    # ----------------------------------------------------------

    def load(self):
        """Load intelligence data and refresh the pattern and symbol indexes."""

        if not self.learning_memory_file.exists():
            self._clear_cache()
            return self.learning_df

        try:
            self.learning_df = pd.read_csv(self.learning_memory_file)
        except pd.errors.EmptyDataError:
            self._clear_cache()
            return self.learning_df

        self._ensure_compatibility_columns()

        self._build_indexes()

        return self.learning_df

    # ----------------------------------------------------------

    def _clear_cache(self):
        self.learning_df = pd.DataFrame()

        self.pattern_index = {}

        self.symbol_index = {}

    # ----------------------------------------------------------

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

    # ----------------------------------------------------------

    @staticmethod
    def _clean_value(value):
        if pd.isna(value):
            return ""

        return str(value).strip()

    # ----------------------------------------------------------

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

    # ----------------------------------------------------------

    def get_dataframe(self):
        return self.learning_df

    # ----------------------------------------------------------

    def get_pattern_index(self):
        return self.pattern_index

    # ----------------------------------------------------------

    def get_symbol_index(self):
        return self.symbol_index
