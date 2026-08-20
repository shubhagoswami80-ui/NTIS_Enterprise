"""
NTIS EOD Predictive Outlook

Presentation layer only.
Consumes existing EOD intelligence outputs; does not run the pipeline.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from EOD_Dashboard.data.data_loader import (
    get_dataset_info,
    load_dataset,
)


def _find_column(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _numeric(df: pd.DataFrame, column: str | None) -> pd.Series:
    if not column:
        return pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _prediction_frame() -> pd.DataFrame:
    ranking = load_dataset("ranking", force_reload=True)
    if ranking is None or ranking.empty:
        return pd.DataFrame()

    result = ranking.copy()

    for dataset in ("probability", "patterns", "outcome"):
        extra = load_dataset(dataset, force_reload=True)
        if extra is None or extra.empty or "Symbol" not in extra.columns:
            continue
        if "Symbol" not in result.columns:
            continue
        result = result.merge(
            extra,
            on="Symbol",
            how="left",
            suffixes=("", f"_{dataset}"),
        )

    return result


def _signal_column(df: pd.DataFrame) -> str | None:
    return _find_column(
        df,
        ["Signal", "Trade Bias", "Bias", "Prediction", "Trade Signal"],
    )


def show_predictive_outlook() -> None:
    st.title("Predictive Outlook")
    st.caption(
        "Next-session intelligence from the existing NTIS EOD outputs. "
        "This page does not execute the production pipeline."
    )

    df = _prediction_frame()

    if df.empty:
        st.warning(
            "No prediction dataset is currently available. "
            "Run the EOD pipeline first."
        )
        return

    signal_col = _signal_column(df)
    score_col = _find_column(
        df,
        ["NTIS Score", "Score", "Final Score", "Total Score"],
    )
    probability_col = _find_column(
        df,
        [
            "Probability",
            "Win Probability",
            "Probability %",
            "Predicted Probability",
        ],
    )
    pattern_col = _find_column(df, ["Pattern", "Pattern Signal"])
    rank_col = _find_column(df, ["Rank", "NTIS Rank", "Ranking"])

    if signal_col:
        signals = df[signal_col].astype(str).str.upper()
        buy_count = int(signals.str.contains("BUY|BULLISH", regex=True).sum())
        sell_count = int(signals.str.contains("SELL|BEARISH", regex=True).sum())
        watch_count = max(len(df) - buy_count - sell_count, 0)
    else:
        buy_count = sell_count = 0
        watch_count = len(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", len(df))
    c2.metric("BUY / Bullish", buy_count)
    c3.metric("SELL / Bearish", sell_count)
    c4.metric("WATCH / Other", watch_count)

    st.divider()
    st.subheader("Next-Session Candidates")

    view = df.copy()

    if signal_col:
        signal = view[signal_col].astype(str).str.upper()
        view["_direction"] = signal.map(
            lambda x: (
                "BUY" if ("BUY" in x or "BULLISH" in x)
                else "SELL" if ("SELL" in x or "BEARISH" in x)
                else "WATCH"
            )
        )
        view = view.sort_values(
            by=["_direction"],
            key=lambda s: s.map({"BUY": 0, "SELL": 1, "WATCH": 2}),
        )

    preferred = [
        c for c in [
            rank_col,
            "Symbol",
            signal_col,
            score_col,
            probability_col,
            pattern_col,
        ]
        if c and c in view.columns
    ]

    if preferred:
        st.dataframe(
            view[preferred].head(25),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.dataframe(
            view.head(25),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Prediction Evidence")

    selected_symbol = st.selectbox(
        "Inspect candidate",
        options=view["Symbol"].astype(str).tolist()
        if "Symbol" in view.columns
        else [],
    )

    if selected_symbol and "Symbol" in view.columns:
        row = view[
            view["Symbol"].astype(str) == selected_symbol
        ].iloc[0]

        evidence_cols = [
            c for c in [
                "Symbol",
                signal_col,
                score_col,
                probability_col,
                pattern_col,
                "Price Chg %",
                "OI Chg %",
                "PCR Chg %",
            ]
            if c and c in view.columns
        ]

        st.dataframe(
            pd.DataFrame([row[evidence_cols].to_dict()]),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Prediction Data Freshness")

    freshness = []
    for dataset in ("ranking", "probability", "patterns", "outcome"):
        info = get_dataset_info(dataset)
        freshness.append(
            {
                "Dataset": dataset,
                "Available": info.get("available", False),
                "Updated": info.get("updated", ""),
            }
        )

    st.dataframe(
        pd.DataFrame(freshness),
        use_container_width=True,
        hide_index=True,
    )
