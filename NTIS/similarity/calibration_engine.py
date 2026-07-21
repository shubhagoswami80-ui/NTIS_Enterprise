"""
=========================================================
NTIS Historical Market Memory Engine
Module  : calibration_engine.py
Version : 1.0.0
Release : HMME-07

Purpose:
    Adjust NTIS probability confidence using historical
    market memory evidence.

Design:
    - Does not replace Probability Engine
    - Adds historical confidence layer
    - Config driven
    - Performance focused
=========================================================
"""

from __future__ import annotations

import logging
import pandas as pd


class CalibrationEngine:

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ):
        self.logger = logger or logging.getLogger(__name__)


    def calibrate(
        self,
        probability_df: pd.DataFrame,
        memory_statistics: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Combine NTIS probability with historical memory evidence.
        """

        if probability_df is None or probability_df.empty:
            return pd.DataFrame()

        result = probability_df.copy()

        if (
            memory_statistics is None
            or memory_statistics.empty
        ):
            result["Historical Confidence"] = "NO DATA"
            result["Calibrated Probability %"] = (
                result.get(
                    "BUY Probability %",
                    0,
                )
            )
            return result


        merge_keys = [
            c for c in [
                "Pattern",
                "Trade Bias",
            ]
            if c in result.columns
            and c in memory_statistics.columns
        ]


        if merge_keys:

            result = result.merge(
                memory_statistics,
                on=merge_keys,
                how="left",
            )


        if "Success Rate %" in result.columns:

            result["Historical Confidence"] = (
                result["Success Rate %"]
                .fillna(0)
                .apply(
                    self._confidence_label
                )
            )

        else:
            result["Historical Confidence"] = "NO DATA"


        if "BUY Probability %" in result.columns:

            history_factor = (
                result.get(
                    "Success Rate %",
                    0,
                )
                .fillna(50)
                / 100
            )

            result["Calibrated Probability %"] = (
                result["BUY Probability %"]
                * 0.7
                +
                history_factor
                * 100
                * 0.3
            ).round(2)


        return result


    def _confidence_label(
        self,
        value,
    ):

        if value >= 80:
            return "HIGH"

        if value >= 60:
            return "MEDIUM"

        return "LOW"
