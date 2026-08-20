import streamlit as st
import pandas as pd


SIGNAL_COLUMNS = (
    "Trade View",
    "Final Signal",
    "Signal",
    "Trade Bias",
    "Validation Signal",
)


SIGNAL_MAP = {
    "BULLISH": "BUY",
    "BUY": "BUY",
    "LONG": "BUY",
    "STRONG BUY": "BUY",
    "BEARISH": "SELL",
    "SELL": "SELL",
    "SHORT": "SELL",
    "STRONG SELL": "SELL",
}


def _normalized_signal_series(df: pd.DataFrame) -> pd.Series:
    result = pd.Series(
        "",
        index=df.index,
        dtype="object",
    )

    for column in SIGNAL_COLUMNS:
        if column not in df.columns:
            continue

        values = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .map(
                lambda value: SIGNAL_MAP.get(
                    value,
                    value,
                )
            )
        )

        usable = result.eq("") & values.ne("")

        result.loc[usable] = values.loc[usable]

    return result


def _count_signal(
    df: pd.DataFrame,
    signal: str,
) -> int:

    if df is None or df.empty:
        return 0

    normalized = _normalized_signal_series(df)

    return int(
        normalized.eq(
            signal.upper()
        ).sum()
    )


def _average_score(
    df: pd.DataFrame,
) -> float:

    for column in (
        "NTIS Score",
        "NTIS Intraday Score",
        "Validation Score",
    ):

        if column not in df.columns:
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce",
        ).dropna()

        if len(values) > 0:
            return round(
                values.mean(),
                2,
            )

    return 0.0


def _high_confidence(
    df: pd.DataFrame,
) -> int:

    if "Confidence" not in df.columns:
        return 0

    values = (
        df["Confidence"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return int(
        values.eq("HIGH").sum()
    )


def show_cards(
    df: pd.DataFrame,
):
    if df is None or df.empty:
        st.warning(
            "No dashboard data available."
        )
        return

    total = len(df)

    buy = _count_signal(
        df,
        "BUY",
    )

    sell = _count_signal(
        df,
        "SELL",
    )

    avg_score = _average_score(
        df,
    )

    high_conf = _high_confidence(
        df,
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Stocks",
        f"{total:,}",
    )

    c2.metric(
        "BUY",
        buy,
    )

    c3.metric(
        "SELL",
        sell,
    )

    c4.metric(
        "Avg Score",
        avg_score,
    )

    c5.metric(
        "High Confidence",
        high_conf,
    )