"""
=========================================================
NTIS Historical Market Memory Engine
Module  : intraday_eod_manager.py
Version : 1.0.0
Release : HMME-08
=========================================================
"""

from __future__ import annotations

import logging
import pandas as pd


class IntradayEODManager:

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def filter_snapshot(
        self,
        data: pd.DataFrame,
        snapshot: str,
    ) -> pd.DataFrame:

        if data is None or data.empty:
            return pd.DataFrame()

        if "Snapshot" not in data.columns:
            return data.copy()

        return data[
            data["Snapshot"] == snapshot
        ].reset_index(drop=True)

    def intraday_compare_set(
        self,
        data: pd.DataFrame,
        snapshot: str,
    ) -> pd.DataFrame:
        """
        Same time comparison:
        Today's 10:00 -> Historical 10:00
        """

        return self.filter_snapshot(
            data,
            snapshot,
        )

    def eod_compare_set(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        if data is None:
            return pd.DataFrame()

        return data.copy()
