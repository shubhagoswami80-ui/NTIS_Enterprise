"""
NTIS-Intraday Dashboard Loader

Purpose:
    Centralized dashboard data loading for the Streamlit UI.
    Refactored from intraday_dashboard.py without changing
    business logic or folder conventions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from config_loader import OUTPUT_ROOT, SCREENSHOT_ROOT
from intraday_latest_snapshot_resolver import IntradayLatestSnapshotResolver


def safe_read(file_path: Path) -> pd.DataFrame:
    """Read CSV if present, otherwise return an empty DataFrame."""
    return pd.read_csv(file_path) if file_path.exists() else pd.DataFrame()


def build_snapshot_path(snapshot_date: str) -> Path:
    dt = datetime.strptime(snapshot_date, "%Y-%m-%d")
    return (
        OUTPUT_ROOT
        / dt.strftime("%Y")
        / dt.strftime("%B")
        / snapshot_date
    )


def resolve_snapshot(requested_date: str | None = None) -> dict:
    if requested_date is None:
        requested_date = datetime.today().strftime("%Y-%m-%d")

    resolver = IntradayLatestSnapshotResolver(
        SCREENSHOT_ROOT,
        OUTPUT_ROOT,
    )

    status = resolver.resolve(requested_date)

    snapshot_date = status.get("snapshot_date")
    base_path = (
        build_snapshot_path(snapshot_date)
        if snapshot_date
        and status.get("status") in {"LIVE", "FALLBACK"}
        else None
    )

    return {
        "requested_date": requested_date,
        "status": status,
        "snapshot_date": snapshot_date,
        "base_path": base_path,
    }


def load_dashboard_data(requested_date: str | None = None) -> dict:
    """
    Load all datasets required by the dashboard.

    Returns a dictionary containing:
      - status
      - snapshot_date
      - trade_df
      - prob_df
      - evolution_df
    """
    ctx = resolve_snapshot(requested_date)

    trade_df = pd.DataFrame()
    prob_df = pd.DataFrame()
    evolution_df = pd.DataFrame()

    if ctx["base_path"] is not None:
        base = ctx["base_path"]

        trade_df = safe_read(
            base / "intraday_trade_candidates.csv"
        )

        prob_df = safe_read(
            base / "intraday_probability_analysis.csv"
        )

        evolution_df = safe_read(
            base / "intraday_signal_evolution.csv"
        )

    ctx.update(
        {
            "trade_df": trade_df,
            "prob_df": prob_df,
            "evolution_df": evolution_df,
        }
    )

    return ctx
