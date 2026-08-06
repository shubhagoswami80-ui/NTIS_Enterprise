"""
NTIS-EOD
Intelligence Builder

Data Preparation Layer

Purpose:
    Combine validated NTIS intelligence outputs
    into a unified dashboard intelligence dataframe.

Rules:
    - Read only
    - No engine logic
    - No scoring changes
    - No probability changes
    - No pattern changes
    - No output file modification
"""

from __future__ import annotations

import pandas as pd

from EOD_Dashboard.data.data_loader import (
    load_dataset,
)


MERGE_KEY = "Symbol"


def _safe_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge two intelligence datasets safely.
    """

    if left.empty:
        return right.copy()

    if right.empty:
        return left.copy()

    if MERGE_KEY not in left.columns:
        return left.copy()

    if MERGE_KEY not in right.columns:
        return left.copy()

    return left.merge(
        right,
        on=MERGE_KEY,
        how="left",
        suffixes=(
            "",
            "_extra",
        ),
    )


def build_intelligence_view() -> pd.DataFrame:
    """
    Build unified NTIS intelligence dataframe.

    Sources:

        ranking
        probability
        patterns
        outcome

    Returns:

        Combined intelligence dataframe
    """

    ranking = load_dataset(
        "ranking"
    )

    if ranking is None:
        return pd.DataFrame()


    intelligence = ranking.copy()


    probability = load_dataset(
        "probability"
    )

    intelligence = _safe_merge(
        intelligence,
        probability
        if probability is not None
        else pd.DataFrame(),
    )


    patterns = load_dataset(
        "patterns"
    )

    intelligence = _safe_merge(
        intelligence,
        patterns
        if patterns is not None
        else pd.DataFrame(),
    )


    outcome = load_dataset(
        "outcome"
    )

    intelligence = _safe_merge(
        intelligence,
        outcome
        if outcome is not None
        else pd.DataFrame(),
    )


    return intelligence


def build_historical_from_runtime() -> dict:
    """
    Fetch historical intelligence payloads directly from the ProductionRuntime result.

    Returns a dict containing the fields already produced by the runtime
    (no calculations, no persistence, no transformations).

    Fields returned (may be None if unavailable):
      - repository_summary
      - historical_intelligence
      - historical_evidence
      - historical_service_summary
      - replay_status
      - calibration_status
      - learning_status

    This function preserves existing dashboard interfaces and returns
    raw objects for the presentation layer to render.
    """

    try:
        from similarity_core_clean.integration.production_runtime import ProductionRuntime

        runtime = ProductionRuntime()
        collected = runtime.run()

        # Support both {'status':..., 'result': {...}} and direct dict
        if isinstance(collected, dict) and "result" in collected:
            payload = collected.get("result") or {}
        elif isinstance(collected, dict):
            payload = collected
        else:
            payload = {}

        return {
            "repository_summary": payload.get("repository_summary"),
            "historical_intelligence": payload.get("historical_intelligence"),
            "historical_evidence": payload.get("historical_evidence"),
            "historical_service_summary": payload.get("historical_service_summary"),
            "replay_status": payload.get("replay_status"),
            "calibration_status": payload.get("calibration_status"),
            "learning_status": payload.get("learning_status"),
        }

    except Exception:
        return {
            "repository_summary": None,
            "historical_intelligence": None,
            "historical_evidence": None,
            "historical_service_summary": None,
            "replay_status": None,
            "calibration_status": None,
            "learning_status": None,
        }


def filter_buy_candidates(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return BUY intelligence candidates.
    """

    if dataframe.empty:
        return dataframe

    if "Signal" not in dataframe.columns:
        return dataframe.iloc[0:0]

    return dataframe[
        dataframe["Signal"]
        .astype(str)
        .str.upper()
        .str.contains(
            "BUY|BULLISH",
            regex=True,
        )
    ].copy()


def filter_sell_candidates(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return SELL intelligence candidates.
    """

    if dataframe.empty:
        return dataframe

    if "Signal" not in dataframe.columns:
        return dataframe.iloc[0:0]

    return dataframe[
        dataframe["Signal"]
        .astype(str)
        .str.upper()
        .str.contains(
            "SELL|BEARISH",
            regex=True,
        )
    ].copy()