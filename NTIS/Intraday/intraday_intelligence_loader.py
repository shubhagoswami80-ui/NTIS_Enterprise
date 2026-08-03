# ----------------------------------------------------------------------
# Bundle 01 - Step 3
# File:
#     intraday_intelligence_loader.py
#
# Purpose:
#     Load NTIS learning intelligence into memory.
# ----------------------------------------------------------------------

from pathlib import Path

import pandas as pd


class IntradayIntelligenceLoader:

    def __init__(

        self,

        learning_memory_file

    ):

        self.learning_memory_file = Path(
            learning_memory_file
        )

        self.learning_df = pd.DataFrame()

        self.pattern_index = {}

        self.symbol_index = {}

    # ----------------------------------------------------------

    def load(self):

        if not self.learning_memory_file.exists():

            self.learning_df = pd.DataFrame()

            self.pattern_index = {}

            self.symbol_index = {}

            return self.learning_df

        self.learning_df = pd.read_csv(
            self.learning_memory_file
        )

        required_columns = [

            "Symbol",

            "Pattern",

            "Pattern_DNA",

            "Pattern_ID"

        ]

        for column in required_columns:

            if column not in self.learning_df.columns:

                self.learning_df[column] = ""

        self._build_indexes()

        return self.learning_df

    # ----------------------------------------------------------

    def _build_indexes(self):

        self.pattern_index = {}

        self.symbol_index = {}

        for idx, row in self.learning_df.iterrows():

            pattern_id = str(
                row["Pattern_ID"]
            ).strip()

            symbol = str(
                row["Symbol"]
            ).strip()

            if pattern_id:

                self.pattern_index.setdefault(

                    pattern_id,

                    []

                ).append(idx)

            if symbol:

                self.symbol_index.setdefault(

                    symbol,

                    []

                ).append(idx)

    # ----------------------------------------------------------

    def get_dataframe(self):

        return self.learning_df

    # ----------------------------------------------------------

    def get_pattern_index(self):

        return self.pattern_index

    # ----------------------------------------------------------

    def get_symbol_index(self):

        return self.symbol_index