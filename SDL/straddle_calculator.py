from __future__ import annotations

import pandas as pd


REQUIRED = ["Symbol", "ATM Straddle %", "Open"]


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def calculate_opening_straddle(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Establish the opening straddle from a reference snapshot.

    Opening Straddle =
        Open * ATM Straddle % / 100

    The pipeline calls this only when establishing the first snapshot
    base for a trading date.
    """
    missing = [c for c in REQUIRED if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing required SDL source columns: {missing}"
        )

    out = df.copy()

    out["daily_open_reference"] = _number(out["Open"])

    out["opening_atm_straddle_pct"] = _number(
        out["ATM Straddle %"]
    )

    out["opening_straddle_premium"] = (
        out["daily_open_reference"]
        * out["opening_atm_straddle_pct"]
        / 100.0
    )

    out["upper_straddle_breakout_level"] = (
        out["daily_open_reference"]
        + out["opening_straddle_premium"]
    )

    out["lower_straddle_breakout_level"] = (
        out["daily_open_reference"]
        - out["opening_straddle_premium"]
    )

    return out


def apply_frozen_opening_straddle(
    df: pd.DataFrame,
    frozen_base_by_symbol: dict,
    current_price_field: str = "Close",
) -> pd.DataFrame:
    """
    Apply the already-frozen opening straddle.

    The ATM Straddle % in this later snapshot is retained as source
    information but is NOT used to change the frozen premium.
    """
    required = [
        "Symbol",
        "Open",
        current_price_field,
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing required SDL source columns: {missing}"
        )

    out = df.copy()

    out["daily_open_reference"] = _number(
        out["Open"]
    )

    out["current_price"] = _number(
        out[current_price_field]
    )

    if "ATM Straddle %" in out.columns:
        out["atm_straddle_pct"] = _number(
            out["ATM Straddle %"]
        )
    else:
        out["atm_straddle_pct"] = pd.NA

    out["opening_straddle_premium"] = (
        out["Symbol"]
        .astype(str)
        .str.strip()
        .map(frozen_base_by_symbol)
    )

    out["upper_straddle_breakout_level"] = (
        out["daily_open_reference"]
        + out["opening_straddle_premium"]
    )

    out["lower_straddle_breakout_level"] = (
        out["daily_open_reference"]
        - out["opening_straddle_premium"]
    )

    out["current_absolute_movement"] = (
        out["current_price"]
        - out["daily_open_reference"]
    ).abs()

    out["upside_breakout"] = (
        out["current_price"].notna()
        & out["upper_straddle_breakout_level"].notna()
        & (
            out["current_price"]
            > out["upper_straddle_breakout_level"]
        )
    )

    out["downside_breakout"] = (
        out["current_price"].notna()
        & out["lower_straddle_breakout_level"].notna()
        & (
            out["current_price"]
            < out["lower_straddle_breakout_level"]
        )
    )

    out["standard_straddle_breakout"] = (
        out["upside_breakout"]
        | out["downside_breakout"]
    )

    out["breakout_direction"] = "NONE"

    out.loc[
        out["upside_breakout"],
        "breakout_direction",
    ] = "UP"

    out.loc[
        out["downside_breakout"],
        "breakout_direction",
    ] = "DOWN"

    valid = (
        out["opening_straddle_premium"].notna()
        & (
            out["opening_straddle_premium"] > 0
        )
        & out["current_absolute_movement"].notna()
    )

    out["movement_vs_opening_straddle_pct"] = pd.NA

    out.loc[
        valid,
        "movement_vs_opening_straddle_pct",
    ] = (
        out.loc[
            valid,
            "current_absolute_movement",
        ]
        / out.loc[
            valid,
            "opening_straddle_premium",
        ]
    ) * 100.0

    if "High" in out.columns:
        high = _number(out["High"])
        out["upside_level_touched"] = (
            high.notna()
            & out["upper_straddle_breakout_level"].notna()
            & (
                high
                > out["upper_straddle_breakout_level"]
            )
        )
    else:
        out["upside_level_touched"] = False

    if "Low" in out.columns:
        low = _number(out["Low"])
        out["downside_level_touched"] = (
            low.notna()
            & out["lower_straddle_breakout_level"].notna()
            & (
                low
                < out["lower_straddle_breakout_level"]
            )
        )
    else:
        out["downside_level_touched"] = False

    return out


# Compatibility functions retained for existing callers.
def derive_straddle_values(
    df: pd.DataFrame,
    breakout_multiplier: float = 1.0,
    current_price_field: str = "Close",
) -> pd.DataFrame:
    base = calculate_opening_straddle(df)

    frozen = dict(
        zip(
            base["Symbol"]
            .astype(str)
            .str.strip(),
            base["opening_straddle_premium"],
        )
    )

    return apply_frozen_opening_straddle(
        base,
        frozen,
        current_price_field,
    )


def derive_current_straddle_premium(
    df: pd.DataFrame,
) -> pd.DataFrame:
    return derive_straddle_values(
        df,
        1.0,
        "Close",
    )


def add_breakout_level(
    df: pd.DataFrame,
    base_premium_by_symbol: dict | None = None,
    multiplier: float = 1.0,
) -> pd.DataFrame:
    if base_premium_by_symbol is None:
        base = calculate_opening_straddle(df)
        base_premium_by_symbol = dict(
            zip(
                base["Symbol"]
                .astype(str)
                .str.strip(),
                base["opening_straddle_premium"],
            )
        )

    return apply_frozen_opening_straddle(
        df,
        base_premium_by_symbol,
        "Close",
    )
