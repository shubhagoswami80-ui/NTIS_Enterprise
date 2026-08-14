from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def append_events(events: pd.DataFrame, path: Path):
    """
    Append only genuinely new first-breakout events.

    The authoritative event uniqueness rule is:
        (trading_date, symbol)

    This is deliberately enforced at the storage boundary as well as in
    pipeline._new_events().  That prevents replaying historical snapshots
    from creating duplicate breakout rows even if the caller is invoked
    repeatedly.

    Existing event rows are never removed or rewritten here.
    """
    if events is None or events.empty:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    new_events = events.copy()

    # Normalize the fields used by the immutable first-breakout key.
    if "trading_date" in new_events.columns:
        new_events["trading_date"] = (
            new_events["trading_date"].astype(str).str.strip()
        )

    if "symbol" in new_events.columns:
        new_events["symbol"] = (
            new_events["symbol"].astype(str).str.strip().str.upper()
        )

    required_key_columns = {"trading_date", "symbol"}

    # If the caller supplies an unexpected schema, preserve the previous
    # behavior rather than silently inventing an event identity.
    if not required_key_columns.issubset(new_events.columns):
        header = not path.exists()
        new_events.to_csv(
            path,
            mode="a",
            index=False,
            header=header,
        )
        return

    # Remove duplicate keys inside the incoming batch itself.
    new_events = new_events.drop_duplicates(
        subset=["trading_date", "symbol"],
        keep="first",
    )

    if new_events.empty:
        return

    if path.exists() and path.stat().st_size > 0:
        existing = pd.read_csv(path)

        if required_key_columns.issubset(existing.columns):
            existing["trading_date"] = (
                existing["trading_date"].astype(str).str.strip()
            )
            existing["symbol"] = (
                existing["symbol"].astype(str).str.strip().str.upper()
            )

            existing_keys = set(
                zip(
                    existing["trading_date"],
                    existing["symbol"],
                )
            )

            new_events = new_events[
                ~new_events.apply(
                    lambda row: (
                        str(row["trading_date"]),
                        str(row["symbol"]),
                    ) in existing_keys,
                    axis=1,
                )
            ]

    if new_events.empty:
        return

    new_events.to_csv(
        path,
        mode="a",
        index=False,
        header=not path.exists() or path.stat().st_size == 0,
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
        "Open",
        "High",
        "Low",
        "Close",
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

    # Append snapshots while preventing exact timestamp + symbol duplication.
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
