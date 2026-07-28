"""
=========================================================
NTIS Historical Market Memory Engine
Module  : memory_index.py
Version : 1.0.0
Release : HMME-05

Purpose:
    Create fast lookup indexes for historical memories.

Design:
    - In-memory index foundation
    - Time snapshot aware
    - Fast filtering before similarity
    - Database migration ready
=========================================================
"""

from __future__ import annotations

import logging
from collections import defaultdict
import pandas as pd


class MemoryIndex:

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ):

        self.logger = logger or logging.getLogger(__name__)

        self.index = defaultdict(list)


    def build(
        self,
        memory_data: pd.DataFrame,
        key_columns: list[str] | None = None,
    ):

        if memory_data is None or memory_data.empty:
            return self.index


        if key_columns is None:

            key_columns = [
                col for col in [
                    "Snapshot",
                    "Pattern",
                    "Trade Bias",
                ]
                if col in memory_data.columns
            ]


        if not key_columns:
            self.index["ALL"] = memory_data.index.tolist()
            return self.index


        grouped = memory_data.groupby(
            key_columns,
            observed=True,
        )


        for key, rows in grouped:

            if not isinstance(key, tuple):
                key = (key,)

            self.index[key] = rows.index.tolist()


        self.logger.info(
            "Memory index created: %s keys",
            len(self.index),
        )


        return self.index


    def lookup(
        self,
        filters: dict,
    ) -> list:

        if not filters:
            return self.index.get(
                "ALL",
                [],
            )


        key = tuple(
            filters.values()
        )

        return self.index.get(
            key,
            [],
        )
