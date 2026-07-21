"""
=========================================================
NTIS Historical Similarity Engine
Module      : feature_normalizer.py
Version     : 1.0.0
Release     : R1
Status      : Production Foundation

Public API
----------
FeatureNormalizer.normalize()
FeatureNormalizer.prepare_features()
=========================================================
"""

from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd


class FeatureNormalizer:
    """Normalize and prepare features for similarity comparison."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def normalize(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce").fillna(0.0)
        minimum = values.min()
        maximum = values.max()

        if maximum == minimum:
            return pd.Series([0.0] * len(values), index=values.index)

        return (values - minimum) / (maximum - minimum)

    def prepare_features(
        self,
        df: pd.DataFrame,
        columns: Iterable[str],
    ) -> pd.DataFrame:
        output = df.copy()

        for column in columns:
            if column not in output.columns:
                self.logger.warning("Missing feature column: %s", column)
                output[column] = 0.0

            output[column] = self.normalize(output[column])

        return output
