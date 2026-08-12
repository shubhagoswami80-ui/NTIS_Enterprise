from __future__ import annotations

import pandas as pd


REQUIRED = [
    "Symbol",
    "ATM Straddle Price",
    "ATM Straddle %",
    "Open",
]


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def derive_straddle_values(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Phase-1 SDL straddle calculation.

    Estimated Initial Straddle:
        Open × ATM Straddle % / 100

    Current Straddle:
        Source ATM Straddle Price

    Breakout:
        Current Straddle >= Estimated Initial Straddle × 1.20
    """

    missing = [
        column
        for column in REQUIRED
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required SDL source columns: {missing}"
        )

    out = df.copy()

    out["daily_open_reference"] = _number(
        out["Open"]
    )

    out["atm_straddle_pct"] = _number(
        out["ATM Straddle %"]
    )

    out["current_straddle_premium"] = _number(
        out["ATM Straddle Price"]
    )

    out["estimated_initial_straddle_premium"] = (
        out["daily_open_reference"]
        * out["atm_straddle_pct"]
        / 100.0
    )

    out["breakout_level"] = (
        out["estimated_initial_straddle_premium"]
        * 1.20
    )

    valid_base = (
        out["estimated_initial_straddle_premium"].notna()
        & (
            out["estimated_initial_straddle_premium"] > 0
        )
        & out["current_straddle_premium"].notna()
    )

    out["expansion_from_estimated_base_pct"] = pd.NA

    out.loc[
        valid_base,
        "expansion_from_estimated_base_pct",
    ] = (
        (
            out.loc[
                valid_base,
                "current_straddle_premium",
            ]
            /
            out.loc[
                valid_base,
                "estimated_initial_straddle_premium",
            ]
        )
        - 1.0
    ) * 100.0

    out["above_breakout_level"] = (
        out["current_straddle_premium"].notna()
        & out["breakout_level"].notna()
        & (
            out["current_straddle_premium"]
            >= out["breakout_level"]
        )
    )

    return out


def derive_current_straddle_premium(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Backward-compatible function name.
    """

    return derive_straddle_values(df)


def add_breakout_level(
    df: pd.DataFrame,
    base_premium_by_symbol: dict | None = None,
    multiplier: float = 1.20,
) -> pd.DataFrame:
    """
    Backward-compatible wrapper.

    The old frozen daily-base map is no longer required.
    """

    if "estimated_initial_straddle_premium" not in df.columns:
        out = derive_straddle_values(df)
    else:
        out = df.copy()

    out["breakout_level"] = (
        out["estimated_initial_straddle_premium"]
        * multiplier
    )

    out["above_breakout_level"] = (
        out["current_straddle_premium"].notna()
        & out["breakout_level"].notna()
        & (
            out["current_straddle_premium"]
            >= out["breakout_level"]
        )
    )

    valid_base = (
        out["estimated_initial_straddle_premium"].notna()
        & (
            out["estimated_initial_straddle_premium"] > 0
        )
        & out["current_straddle_premium"].notna()
    )

    out["expansion_from_estimated_base_pct"] = pd.NA

    out.loc[
        valid_base,
        "expansion_from_estimated_base_pct",
    ] = (
        (
            out.loc[
                valid_base,
                "current_straddle_premium",
            ]
            /
            out.loc[
                valid_base,
                "estimated_initial_straddle_premium",
            ]
        )
        - 1.0
    ) * 100.0

    return out
