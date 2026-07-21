"""
=========================================================
NTIS Historical Market Memory Engine
Module  : outcome_filter.py
Version : 1.0.0
Release : HMME-02

Purpose:
    Extract meaningful historical market experiences from
    existing NTIS outcome reports.

Design:
    - Reuses Outcome Engine output
    - No duplicate outcome calculation
    - Vectorized filtering
    - Performance focused
=========================================================
"""

from __future__ import annotations

import logging
import pandas as pd

from Config.hmme_config import OUTCOME_FILTER_CONFIG


class OutcomeFilter:

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)

        self.minimum_move = OUTCOME_FILTER_CONFIG[
            "minimum_move_percent"
        ]

        self.strong_move = OUTCOME_FILTER_CONFIG[
            "strong_move_percent"
        ]

        self.direction_sensitive = OUTCOME_FILTER_CONFIG[
            "direction_sensitive"
        ]


    def filter(self, outcome_data: pd.DataFrame) -> pd.DataFrame:
        """
        Return historically successful meaningful moves.
        """

        if outcome_data is None or outcome_data.empty:
            return pd.DataFrame()

        required = [
            "Trade Bias",
            "Actual Return %",
        ]

        missing = [
            c for c in required
            if c not in outcome_data.columns
        ]

        if missing:
            raise ValueError(
                f"Missing required columns: {missing}"
            )


        df = outcome_data.copy()


        # Memory optimization for large history
        for col in [
            "Symbol",
            "Pattern",
            "Trade Bias",
            "Outcome",
        ]:
            if col in df.columns:
                df[col] = df[col].astype("category")


        df["Actual Return %"] = pd.to_numeric(
            df["Actual Return %"],
            errors="coerce",
        )

        df = df.dropna(
            subset=["Actual Return %"]
        )


        if self.direction_sensitive:

            buy_mask = (
                df["Trade Bias"]
                .astype(str)
                .str.upper()
                .isin(["BUY", "STRONG BUY"])
                &
                (
                    df["Actual Return %"]
                    >= self.minimum_move
                )
            )


            sell_mask = (
                df["Trade Bias"]
                .astype(str)
                .str.upper()
                .eq("SELL")
                &
                (
                    df["Actual Return %"]
                    <= -self.minimum_move
                )
            )


            df = df[
                buy_mask | sell_mask
            ]

        else:

            df = df[
                df["Actual Return %"].abs()
                >= self.minimum_move
            ]


        self.logger.info(
            "Outcome Filter qualified %s records",
            len(df),
        )


        return df.reset_index(drop=True)


    def classify_strength(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        """
        Add movement strength classification.
        """

        if df.empty:
            return df


        result = df.copy()

        result["Move Strength"] = "NORMAL"


        result.loc[
            result["Actual Return %"].abs()
            >= self.strong_move,
            "Move Strength"
        ] = "STRONG"


        return result
