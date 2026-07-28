"""
=========================================================
NTIS Historical Market Memory Engine
Module      : candidate_selector.py
Version     : 1.0.0
Release     : HMME-01

Purpose:
    Select relevant historical market states before
    expensive similarity calculations.

Design:
    - Performance first
    - No probability logic
    - No trading decision logic
    - Configurable filtering

=========================================================
"""

from __future__ import annotations

import logging
import pandas as pd


class CandidateSelector:
    """
    Filters historical market states to create a focused
    candidate pool for similarity analysis.
    """

    def __init__(
        self,
        score_window: int = 10,
        require_pattern_match: bool = True,
        require_trade_bias_match: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self.score_window = score_window
        self.require_pattern_match = require_pattern_match
        self.require_trade_bias_match = require_trade_bias_match
        self.logger = logger or logging.getLogger(__name__)

    def select(
        self,
        current_market_state: dict | pd.Series,
        historical_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Select historical records relevant to current market state.
        """

        if historical_data is None or historical_data.empty:
            return pd.DataFrame()

        df = historical_data.copy()

        df = self._clean_data(df)

        if self.require_trade_bias_match:
            df = self._filter_trade_bias(
                current_market_state,
                df,
            )

        if self.require_pattern_match:
            df = self._filter_pattern(
                current_market_state,
                df,
            )

        df = self._filter_score(
            current_market_state,
            df,
        )

        self.logger.info(
            "Candidate Selector returned %s records",
            len(df),
        )

        return df.reset_index(drop=True)

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        required = [
            "Symbol",
            "NTIS Score",
        ]

        available = [
            col for col in required
            if col in df.columns
        ]

        if available:
            df = df.dropna(subset=available)

        return df

    def _filter_trade_bias(
        self,
        current,
        df,
    ):
        if "Trade Bias" not in df.columns:
            return df

        bias = self._get_value(
            current,
            "Trade Bias",
        )

        if bias is None:
            return df

        return df[
            df["Trade Bias"].astype(str).str.upper()
            == str(bias).upper()
        ]

    def _filter_pattern(
        self,
        current,
        df,
    ):
        if "Pattern" not in df.columns:
            return df

        pattern = self._get_value(
            current,
            "Pattern",
        )

        if pattern is None:
            return df

        return df[
            df["Pattern"].astype(str)
            == str(pattern)
        ]

    def _filter_score(
        self,
        current,
        df,
    ):
        if "NTIS Score" not in df.columns:
            return df

        score = self._get_value(
            current,
            "NTIS Score",
        )

        if score is None:
            return df

        low = score - self.score_window
        high = score + self.score_window

        return df[
            df["NTIS Score"].between(
                low,
                high,
            )
        ]

    @staticmethod
    def _get_value(
        source,
        key,
    ):
        if isinstance(source, dict):
            return source.get(key)

        if isinstance(source, pd.Series):
            return source.get(key)

        return getattr(source, key, None)
