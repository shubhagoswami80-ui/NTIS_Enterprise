from __future__ import annotations

from pathlib import Path

import pandas as pd


APPROACHING_MULTIPLIER = 0.50

APPROACHING_COLUMNS = [
    "trading_date",
    "observation_timestamp",
    "symbol",
    "direction",
    "open_price",
    "current_price",
    "opening_straddle_premium",
    "approaching_level",
    "breakout_level",
    "distance_to_breakout",
    "approach_progress_pct",
]


def calculate_approaching_breakouts(
    df: pd.DataFrame,
    approaching_multiplier: float = APPROACHING_MULTIPLIER,
) -> pd.DataFrame:
    """
    Calculate stocks that reached >=50% of their own frozen opening straddle
    but are still below the exact 1x breakout boundary.

    UP:
        open + 0.5x straddle <= current < open + 1.0x straddle

    DOWN:
        open - 1.0x straddle < current <= open - 0.5x straddle
    """
    out = df.copy()

    required = {
        "Symbol",
        "daily_open_reference",
        "current_price",
        "opening_straddle_premium",
        "upper_straddle_breakout_level",
        "lower_straddle_breakout_level",
    }
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(
            "Approaching-breakout calculation missing columns: "
            + ", ".join(missing)
        )

    premium = pd.to_numeric(out["opening_straddle_premium"], errors="coerce")
    opening = pd.to_numeric(out["daily_open_reference"], errors="coerce")
    current = pd.to_numeric(out["current_price"], errors="coerce")

    out["approaching_upper_level"] = (
        opening + premium * approaching_multiplier
    )
    out["approaching_lower_level"] = (
        opening - premium * approaching_multiplier
    )

    up = (
        current >= out["approaching_upper_level"]
    ) & (
        current < out["upper_straddle_breakout_level"]
    )

    down = (
        current <= out["approaching_lower_level"]
    ) & (
        current > out["lower_straddle_breakout_level"]
    )

    out["approaching_breakout_direction"] = "NONE"
    out.loc[up, "approaching_breakout_direction"] = "UP"
    out.loc[down, "approaching_breakout_direction"] = "DOWN"

    out["approaching_breakout"] = up | down

    out["approaching_breakout_distance"] = pd.NA
    out.loc[up, "approaching_breakout_distance"] = (
        out.loc[up, "upper_straddle_breakout_level"] - current.loc[up]
    )
    out.loc[down, "approaching_breakout_distance"] = (
        current.loc[down] - out.loc[down, "lower_straddle_breakout_level"]
    )

    out["approach_progress_pct"] = (
        (current - opening).abs() / premium * 100.0
    )

    return out


def approaching_breakout_view(
    df: pd.DataFrame,
    trading_date: str,
    observation_timestamp,
) -> pd.DataFrame:
    calculated = calculate_approaching_breakouts(df)
    result = calculated[calculated["approaching_breakout"]].copy()

    if result.empty:
        return pd.DataFrame(columns=APPROACHING_COLUMNS)

    result["trading_date"] = str(trading_date)
    result["observation_timestamp"] = (
        pd.Timestamp(observation_timestamp).isoformat()
    )
    result["symbol"] = (
        result["Symbol"].astype(str).str.strip().str.upper()
    )
    result["direction"] = result["approaching_breakout_direction"]
    result["open_price"] = result["daily_open_reference"]

    result["approaching_level"] = result.apply(
        lambda row: (
            row["approaching_upper_level"]
            if row["direction"] == "UP"
            else row["approaching_lower_level"]
        ),
        axis=1,
    )
    result["breakout_level"] = result.apply(
        lambda row: (
            row["upper_straddle_breakout_level"]
            if row["direction"] == "UP"
            else row["lower_straddle_breakout_level"]
        ),
        axis=1,
    )
    result["distance_to_breakout"] = result[
        "approaching_breakout_distance"
    ]

    return (
        result[APPROACHING_COLUMNS]
        .sort_values(
            ["approach_progress_pct", "symbol"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )


def _read_existing(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=APPROACHING_COLUMNS)

    existing = pd.read_csv(path)

    if not set(APPROACHING_COLUMNS).issubset(existing.columns):
        return pd.DataFrame(columns=APPROACHING_COLUMNS)

    existing = existing[APPROACHING_COLUMNS].copy()
    existing["trading_date"] = (
        existing["trading_date"]
        .map(lambda value: pd.to_datetime(value, errors="coerce"))
        .dt.strftime("%Y-%m-%d")
    )
    existing["symbol"] = (
        existing["symbol"].astype(str).str.strip().str.upper()
    )

    return existing.drop_duplicates(
        subset=["trading_date", "symbol"],
        keep="first",
    )


def save_approaching_breakouts(
    df: pd.DataFrame,
    trading_date: str,
    observation_timestamp,
    path: Path,
) -> pd.DataFrame:
    """
    Append-only historical 50% layer.

    Authoritative uniqueness:
        (trading_date, symbol)

    First qualifying observation wins.
    Later snapshots never rewrite the first record.
    Reaching 100% does not delete the 50% record.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    current = approaching_breakout_view(
        df,
        trading_date,
        observation_timestamp,
    )

    if current.empty:
        return current

    existing = _read_existing(path)

    current["trading_date"] = str(trading_date)
    current["symbol"] = (
        current["symbol"].astype(str).str.strip().str.upper()
    )

    existing_keys = set(
        zip(existing["trading_date"], existing["symbol"])
    )

    new_rows = current[
        ~current.apply(
            lambda row: (
                str(row["trading_date"]),
                str(row["symbol"]),
            ) in existing_keys,
            axis=1,
        )
    ].copy()

    if new_rows.empty:
        return new_rows.reset_index(drop=True)

    combined = pd.concat(
        [existing, new_rows],
        ignore_index=True,
    )

    combined = combined.drop_duplicates(
        subset=["trading_date", "symbol"],
        keep="first",
    )
    combined = combined[APPROACHING_COLUMNS]

    temp = path.with_suffix(".tmp")
    combined.to_csv(temp, index=False)
    temp.replace(path)

    return new_rows.reset_index(drop=True)


def load_approaching_breakouts(path: Path) -> pd.DataFrame:
    return _read_existing(Path(path))


def load_latest_approaching_breakouts(path: Path) -> pd.DataFrame:
    # Compatibility name used by the earlier dashboard integration.
    return _read_existing(Path(path))
