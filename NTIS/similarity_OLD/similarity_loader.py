"""
=========================================================
NTIS Historical Similarity Engine
Module      : similarity_loader.py
Version     : 1.0.0
Release     : R1
Status      : Production Foundation

Public API
----------
SimilarityLoader.load_csv()
SimilarityLoader.load_market_master()
SimilarityLoader.load_probability()
SimilarityLoader.load_history()
=========================================================
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd


class SimilarityLoader:
    """Loads and validates NTIS input datasets."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def load_csv(
        self,
        file_path: str | Path,
        required_columns: Iterable[str] | None = None,
    ) -> pd.DataFrame:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        df = pd.read_csv(path)

        if required_columns:
            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                raise ValueError(
                    f"{path.name} is missing required columns: {', '.join(missing)}"
                )

        df.columns = [c.strip() for c in df.columns]
        return df

    def load_market_master(self, file_path: str | Path) -> pd.DataFrame:
        return self.load_csv(file_path, required_columns=["Symbol"])

    def load_probability(self, file_path: str | Path) -> pd.DataFrame:
        return self.load_csv(
            file_path,
            required_columns=["Symbol", "BUY Probability %"],
        )

    def load_history(self, file_path: str | Path) -> pd.DataFrame:
        return self.load_csv(file_path)
