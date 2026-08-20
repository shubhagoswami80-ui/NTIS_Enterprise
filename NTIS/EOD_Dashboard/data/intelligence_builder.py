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

    Only columns that do not already exist in the left dataframe are
    imported from the right dataframe. This prevents repeated merges
    from generating duplicate *_extra columns and preserves the
    ranking dataframe as the primary/base dataset.
    """

    if left.empty:
        return right.copy()

    if right.empty:
        return left.copy()

    if MERGE_KEY not in left.columns:
        return left.copy()

    if MERGE_KEY not in right.columns:
        return left.copy()

    right_columns = [
        column
        for column in right.columns
        if column != MERGE_KEY
        and column not in left.columns
    ]

    if not right_columns:
        return left.copy()

    right_unique = right[
        [MERGE_KEY, *right_columns]
    ].copy()

    return left.merge(
        right_unique,
        on=MERGE_KEY,
        how="left",
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
        Combined intelligence dataframe.
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
    Fetch historical intelligence payloads directly from the
    ProductionRuntime result.

    Returns a dict containing the fields already produced by the
    runtime.

    No calculations, persistence, or transformations are performed.

    Fields returned:
        repository_summary
        historical_intelligence
        historical_evidence
        historical_service_summary
        replay_status
        calibration_status
        learning_status
        candidate_ranking
    """

    try:
        from similarity_core_clean.integration.production_runtime import (
            ProductionRuntime,
        )

        runtime = ProductionRuntime()
        collected = runtime.run()

        if (
            isinstance(collected, dict)
            and "result" in collected
        ):
            payload = (
                collected.get("result")
                or {}
            )

        elif isinstance(
            collected,
            dict,
        ):
            payload = collected

        else:
            payload = {}

        return {
            "repository_summary":
                payload.get(
                    "repository_summary"
                ),
            "historical_intelligence":
                payload.get(
                    "historical_intelligence"
                ),
            "historical_evidence":
                payload.get(
                    "historical_evidence"
                ),
            "historical_service_summary":
                payload.get(
                    "historical_service_summary"
                ),
            "replay_status":
                payload.get(
                    "replay_status"
                ),
            "calibration_status":
                payload.get(
                    "calibration_status"
                ),
            "learning_status":
                payload.get(
                    "learning_status"
                ),
            "candidate_ranking":
                payload.get(
                    "candidate_ranking"
                ),
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
            "candidate_ranking": None,
        }


def _candidate_signal_series(
    dataframe: pd.DataFrame,
) -> pd.Series:
    """
    Return the signal series used by candidate filters.

    Trade View is preferred because market_overview.py normalizes
    the signal into this field before calling the candidate filters.

    Signal remains the fallback for callers that invoke these filters
    before Trade View has been created.
    """

    if "Trade View" in dataframe.columns:
        trade_view = (
            dataframe["Trade View"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        if trade_view.ne("").any():
            return trade_view

    if "Signal" in dataframe.columns:
        return (
            dataframe["Signal"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

    return pd.Series(
        "",
        index=dataframe.index,
        dtype="object",
    )


def filter_buy_candidates(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return BUY intelligence candidates.

    Uses the dashboard-normalized Trade View when available,
    with Signal as the fallback.
    """

    if dataframe.empty:
        return dataframe

    signal_series = _candidate_signal_series(
        dataframe
    )

    return dataframe[
        signal_series.str.contains(
            "BUY|BULLISH",
            regex=True,
            na=False,
        )
    ].copy()


def filter_sell_candidates(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return SELL intelligence candidates.

    Uses the dashboard-normalized Trade View when available,
    with Signal as the fallback.
    """

    if dataframe.empty:
        return dataframe

    signal_series = _candidate_signal_series(
        dataframe
    )

    return dataframe[
        signal_series.str.contains(
            "SELL|BEARISH",
            regex=True,
            na=False,
        )
    ].copy()