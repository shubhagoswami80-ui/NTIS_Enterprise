"""
=========================================================
NTIS Historical Market Memory Engine
Module  : memory_repository.py
Version : 1.0.0
Release : HMME-04

Purpose:
    Store and retrieve learned historical market memories.

Design:
    - CSV based foundation
    - Database migration ready
    - No trading decisions
    - Reusable learning output
=========================================================
"""

from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd


class MemoryRepository:

    def __init__(
        self,
        storage_file: str | Path,
        logger: logging.Logger | None = None,
    ):

        self.storage_file = Path(storage_file)
        self.logger = logger or logging.getLogger(__name__)


    def save(
        self,
        memory_data: pd.DataFrame,
    ) -> None:

        if memory_data is None or memory_data.empty:
            return

        self.storage_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        memory_data.to_csv(
            self.storage_file,
            index=False,
        )

        self.logger.info(
            "Memory repository saved: %s records",
            len(memory_data),
        )


    def load(self) -> pd.DataFrame:

        if not self.storage_file.exists():
            return pd.DataFrame()

        return pd.read_csv(
            self.storage_file
        )


    def update(
        self,
        new_memory: pd.DataFrame,
    ) -> pd.DataFrame:

        existing = self.load()

        if existing.empty:
            combined = new_memory.copy()

        else:
            combined = pd.concat(
                [
                    existing,
                    new_memory,
                ],
                ignore_index=True,
            )

            combined = combined.drop_duplicates()

        self.save(combined)

        return combined
