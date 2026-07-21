"""
=========================================================
NTIS Historical Market Memory Engine
Module  : learning_statistics.py
Version : 1.0.0
Release : HMME-03

Purpose:
    Convert qualified historical market memories into
    statistical intelligence.

Design:
    - Vectorized pandas operations
    - No row loops
    - Incremental learning ready
    - Performance focused
=========================================================
"""

from __future__ import annotations

import logging
import pandas as pd

from Config.hmme_config import LEARNING_STATISTICS_CONFIG


class LearningStatistics:

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)

        self.minimum_sample_size = LEARNING_STATISTICS_CONFIG[
            "minimum_sample_size"
        ]

        self.confidence_levels = LEARNING_STATISTICS_CONFIG[
            "confidence_levels"
        ]


    def calculate(
        self,
        historical_memory: pd.DataFrame,
        group_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Generate learning statistics from qualified memories.
        """

        if historical_memory is None or historical_memory.empty:
            return pd.DataFrame()

        df = historical_memory.copy()

        required = [
            "Actual Return %",
        ]

        missing = [
            c for c in required
            if c not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing required columns: {missing}"
            )

        df["Actual Return %"] = pd.to_numeric(
            df["Actual Return %"],
            errors="coerce",
        )

        df = df.dropna(
            subset=["Actual Return %"]
        )

        if group_columns is None:
            group_columns = [
                col for col in [
                    "Pattern",
                    "Trade Bias",
                ]
                if col in df.columns
            ]

        if not group_columns:
            group_columns = ["Trade Bias"] if "Trade Bias" in df.columns else []

        if group_columns:

            result = (
                df.groupby(group_columns)
                .agg(
                    Samples=("Actual Return %", "count"),
                    Average_Move=("Actual Return %", "mean"),
                    Max_Move=("Actual Return %", "max"),
                    Min_Move=("Actual Return %", "min"),
                )
                .reset_index()
            )

            success = (
                df.assign(
                    Success=df["Actual Return %"].abs() >= 1.5
                )
                .groupby(group_columns)["Success"]
                .mean()
                .reset_index(name="Success_Rate")
            )

            result = result.merge(
                success,
                on=group_columns,
                how="left",
            )

        else:

            result = pd.DataFrame(
                {
                    "Samples": [
                        len(df)
                    ],
                    "Average_Move": [
                        df["Actual Return %"].mean()
                    ],
                }
            )

            result["Success_Rate"] = (
                df["Actual Return %"]
                .abs()
                .ge(1.5)
                .mean()
            )


        result["Success Rate %"] = (
            result["Success_Rate"] * 100
        ).round(2)

        result["Average Move %"] = (
            result["Average_Move"]
        ).round(2)

        result["Confidence"] = result.apply(
            self._confidence,
            axis=1,
        )

        self.logger.info(
            "Learning statistics generated: %s records",
            len(result),
        )

        return result


    def _confidence(self, row):

        samples = row.get(
            "Samples",
            0,
        )

        rate = row.get(
            "Success Rate %",
            0,
        )

        if samples >= self.minimum_sample_size and rate >= 80:
            return "HIGH"

        if samples >= self.minimum_sample_size and rate >= 60:
            return "MEDIUM"

        return "LOW"
