from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def append_events(events: pd.DataFrame, path: Path):
    if events.empty:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    header = not path.exists()

    events.to_csv(
        path,
        mode="a",
        index=False,
        header=header,
    )


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def save_state(state: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, default=str),
        encoding="utf-8",
    )


def save_daily_evidence(
    df: pd.DataFrame,
    trading_date: str,
    evidence_root: Path,
    observation_timestamp=None,
):
    """
    Preserve required evidence without copying the source workbook.

    The evidence file is SDL-owned and contains calculated/source fields
    required for later replay. Source Excel files remain at their original
    external location.
    """

    evidence_root.mkdir(parents=True, exist_ok=True)

    if df.empty:
        return

    evidence = df.copy()
    evidence["trading_date"] = trading_date
    evidence["observation_timestamp"] = (
        pd.Timestamp(observation_timestamp).isoformat()
        if observation_timestamp is not None
        else pd.NA
    )

    columns = [
        "trading_date",
        "observation_timestamp",
        "Symbol",
        "Open", "High", "Low", "Close",
        "ATM Straddle %",
        "current_price",
        "opening_straddle_premium",
        "upper_straddle_breakout_level",
        "lower_straddle_breakout_level",
        "upside_breakout",
        "downside_breakout",
        "standard_straddle_breakout",
        "breakout_direction",
        "Price Chg %",
        "IV Chg %",
        "OI Chg %",
        "PCR Chg %",
    ]

    keep = [c for c in columns if c in evidence.columns]

    day_file = evidence_root / f"{trading_date}.csv"

    # Append snapshots while preventing exact timestamp duplication.
    new_rows = evidence[keep].copy()

    if day_file.exists():
        old = pd.read_csv(day_file)

        if "observation_timestamp" in old.columns:
            existing_keys = set(
                zip(
                    old["observation_timestamp"].astype(str),
                    old["Symbol"].astype(str),
                )
            )

            new_rows = new_rows[
                ~new_rows.apply(
                    lambda r: (
                        str(r["observation_timestamp"]),
                        str(r["Symbol"]),
                    ) in existing_keys,
                    axis=1,
                )
            ]

        if new_rows.empty:
            return

        new_rows.to_csv(
            day_file,
            mode="a",
            index=False,
            header=False,
        )
    else:
        new_rows.to_csv(
            day_file,
            index=False,
        )
