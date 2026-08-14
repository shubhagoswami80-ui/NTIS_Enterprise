from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


EVENT_COLUMNS = [
    "event_id",
    "trading_date",
    "observation_timestamp",
    "symbol",
    "direction",
    "status",
    "open_price",
    "current_price",
    "expected_1x_price",
    "expected_1x_move",
    "breakout_distance",
    "price_chg_pct",
    "high",
    "low",
    "atm_straddle_pct",
    "opening_straddle_premium",
    "source_atm_straddle_price",
    "iv_chg_pct",
    "oi_chg_pct",
    "pcr_chg_pct",
    "ce_oi_chg_pct",
    "pe_oi_chg_pct",
    "pe_minus_ce_oi_chg",
    "strategy_version",
]


def load_events(path: Path) -> pd.DataFrame:
    """
    Load the authoritative event CSV.

    The CSV schema is normalized to EVENT_COLUMNS when possible.
    No rows are removed or rewritten here.
    """
    if not path.exists():
        return pd.DataFrame(columns=EVENT_COLUMNS)

    df = pd.read_csv(path)

    return df


def _event_id(trading_date: str, symbol: str) -> str:
    """
    Generate a deterministic event ID.

    Event identity is intentionally based on the authoritative
    first-breakout uniqueness key:

        (trading_date, symbol)
    """
    key = f"{trading_date}|{symbol}".encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:20]


def _prepare_event_rows(events: pd.DataFrame) -> pd.DataFrame:
    """
    Convert an event DataFrame into the exact persistent event schema.

    IMPORTANT:
        event_id is generated here because pipeline._new_events()
        intentionally returns the business event fields without
        persistence-specific identity.

        The final column order is always EVENT_COLUMNS.

    This prevents CSV column shifting/corruption.
    """
    if events is None or events.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    new_events = events.copy()

    # ---------------------------------------------------------------
    # Required business-key normalization
    # ---------------------------------------------------------------

    if "trading_date" not in new_events.columns:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    if "symbol" not in new_events.columns:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    new_events["trading_date"] = (
        new_events["trading_date"]
        .astype(str)
        .str.strip()
    )

    new_events["symbol"] = (
        new_events["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Reject rows without a valid business key.
    new_events = new_events[
        new_events["trading_date"].ne("")
        & new_events["symbol"].ne("")
        & new_events["trading_date"].ne("nan")
    ].copy()

    if new_events.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    # ---------------------------------------------------------------
    # Persistence identity
    # ---------------------------------------------------------------

    new_events["event_id"] = new_events.apply(
        lambda row: _event_id(
            str(row["trading_date"]),
            str(row["symbol"]),
        ),
        axis=1,
    )

    # ---------------------------------------------------------------
    # Ensure every persistent column exists.
    # ---------------------------------------------------------------

    for column in EVENT_COLUMNS:
        if column not in new_events.columns:
            new_events[column] = pd.NA

    # ---------------------------------------------------------------
    # AUTHORITATIVE persistent order.
    #
    # This is the critical protection against the previous
    # event_id/trading_date/observation_timestamp column shift.
    # ---------------------------------------------------------------

    new_events = new_events[EVENT_COLUMNS].copy()

    return new_events


def append_events(
    events: pd.DataFrame,
    path: Path,
):
    """
    Append only genuinely new first-breakout events.

    Authoritative event uniqueness:

        (trading_date, symbol)

    Storage guarantees:

    1. Incoming events are normalized.
    2. event_id is generated at the storage boundary.
    3. Incoming columns are forced into EVENT_COLUMNS order.
    4. Duplicate keys inside the incoming batch are removed.
    5. Existing event keys are loaded before append.
    6. Existing events are never removed or rewritten.
    7. A replay cannot append the same trading-date/symbol again.
    """

    if events is None or events.empty:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    new_events = _prepare_event_rows(events)

    if new_events.empty:
        return

    # ---------------------------------------------------------------
    # Remove duplicate keys inside this incoming batch.
    # ---------------------------------------------------------------

    new_events = new_events.drop_duplicates(
        subset=["trading_date", "symbol"],
        keep="first",
    )

    if new_events.empty:
        return

    # ---------------------------------------------------------------
    # Existing file
    # ---------------------------------------------------------------

    if path.exists() and path.stat().st_size > 0:

        existing = pd.read_csv(path)

        # If an existing file is structurally incompatible, do NOT
        # append into it. This prevents another silent corruption.
        if not set(EVENT_COLUMNS).issubset(existing.columns):
            raise ValueError(
                "Existing event CSV schema is incompatible with "
                "EVENT_COLUMNS. Repair the event CSV before appending."
            )

        existing["trading_date"] = (
            existing["trading_date"]
            .astype(str)
            .str.strip()
        )

        existing["symbol"] = (
            existing["symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
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
        ].copy()

    if new_events.empty:
        return

    # ---------------------------------------------------------------
    # Final schema/order enforcement immediately before writing.
    # ---------------------------------------------------------------

    new_events = new_events[EVENT_COLUMNS]

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


def save_state(
    state: dict,
    path: Path,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            state,
            indent=2,
            default=str,
        ),
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

    Source Excel files remain at their original external location.
    """

    evidence_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    if df.empty:
        return

    evidence = df.copy()

    evidence["trading_date"] = trading_date

    evidence["observation_timestamp"] = (
        pd.Timestamp(
            observation_timestamp
        ).isoformat()
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

    keep = [
        column
        for column in columns
        if column in evidence.columns
    ]

    if not keep:
        return

    new_rows = evidence[keep].copy()

    day_file = (
        evidence_root
        / f"{trading_date}.csv"
    )

    if day_file.exists():

        old = pd.read_csv(day_file)

        if (
            "observation_timestamp" in old.columns
            and "Symbol" in old.columns
            and "observation_timestamp"
            in new_rows.columns
            and "Symbol"
            in new_rows.columns
        ):

            existing_keys = set(
                zip(
                    old[
                        "observation_timestamp"
                    ].astype(str),
                    old["Symbol"]
                    .astype(str)
                    .str.upper(),
                )
            )

            new_rows = new_rows[
                ~new_rows.apply(
                    lambda row: (
                        str(
                            row[
                                "observation_timestamp"
                            ]
                        ),
                        str(
                            row["Symbol"]
                        ).upper(),
                    )
                    in existing_keys,
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