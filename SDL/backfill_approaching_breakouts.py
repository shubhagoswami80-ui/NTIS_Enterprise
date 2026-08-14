from __future__ import annotations

"""
SDL — 12-Aug-2026-only 50% approaching-breakout backfill.

This is deliberately date-scoped. It never discovers or processes
older historical dates.

Source files are read only.

Uniqueness:
    (trading_date, symbol)

First qualifying >=50% observation wins. Later observations, including
100% breakout observations, never create another 50% record.
"""

from pathlib import Path
from datetime import datetime
import pandas as pd

import pipeline
from approaching_breakout import approaching_breakout_view


TARGET_DATE = "2026-08-12"
TARGET = Path(pipeline.EVENT_CSV).parent / "approaching_breakouts.csv"


def _snapshot_timestamp(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def _load_existing() -> pd.DataFrame:
    if not TARGET.exists() or TARGET.stat().st_size == 0:
        return pd.DataFrame()

    df = pd.read_csv(TARGET)

    if not {"trading_date", "symbol"}.issubset(df.columns):
        return pd.DataFrame()

    df["trading_date"] = (
        pd.to_datetime(df["trading_date"], errors="coerce")
        .dt.strftime("%Y-%m-%d")
    )
    df["symbol"] = (
        df["symbol"].astype(str).str.strip().str.upper()
    )

    # Preserve only the first record for each stock/day.
    return df.drop_duplicates(
        subset=["trading_date", "symbol"],
        keep="first",
    ).reset_index(drop=True)


def run() -> None:
    files = sorted(
        pipeline.discover_historical_snapshots(TARGET_DATE),
        key=lambda p: p.stat().st_mtime,
    )

    print("TARGET DATE:", TARGET_DATE)
    print("TARGET:", TARGET)
    print("FILES:", len(files))

    if not files:
        raise RuntimeError(
            f"No historical snapshots found for {TARGET_DATE}"
        )

    # IMPORTANT:
    # Only the requested date is processed. No repository-wide scan.
    files = [
        Path(p)
        for p in files
        if TARGET_DATE in str(p)
    ]

    print("DATE-SCOPED FILES:", len(files))

    state = pipeline.load_state(pipeline.STATE_JSON)

    # Establish the frozen daily base from the FIRST snapshot only.
    first_path = files[0]
    first_ts = _snapshot_timestamp(first_path)

    first_df, _ = pipeline.load_primary_snapshot(
        first_path,
        first_ts,
    )

    first_df = pipeline.derive_straddle_values(
        first_df,
        breakout_multiplier=pipeline.BREAKOUT_MULTIPLIER,
        current_price_field=pipeline.CURRENT_PRICE_FIELD,
    )

    # Use an isolated state copy so this backfill does not alter live state.
    isolated_state = dict(state)

    base_map = pipeline._ensure_first_snapshot_base(
        df=first_df,
        state=isolated_state,
        trading_date=TARGET_DATE,
        source_path=first_path,
        observed_at=first_ts,
    )

    print("FIRST SNAPSHOT:", first_path.name)
    print("BASE SYMBOLS:", len(base_map))

    existing = _load_existing()

    # For this fix, remove any pre-existing 12-Aug records so the file
    # is reconstructed authoritatively from the four validated snapshots.
    if not existing.empty:
        existing = existing[
            existing["trading_date"] != TARGET_DATE
        ].copy()

    seen = set(
        zip(
            existing["trading_date"],
            existing["symbol"],
        )
    ) if not existing.empty else set()

    new_rows = []

    print("--- 12-AUG 50% REPLAY ---")

    for path in files:
        observed_at = _snapshot_timestamp(path)

        df, _ = pipeline.load_primary_snapshot(
            path,
            observed_at,
        )

        df = pipeline.derive_straddle_values(
            df,
            breakout_multiplier=pipeline.BREAKOUT_MULTIPLIER,
            current_price_field=pipeline.CURRENT_PRICE_FIELD,
        )

        df = pipeline._apply_frozen_base(
            df,
            base_map,
        )

        current = approaching_breakout_view(
            df,
            TARGET_DATE,
            observed_at,
        )

        print(
            path.name,
            "|",
            observed_at.isoformat(),
            "| APPROACHING:",
            len(current),
        )

        for _, row in current.iterrows():
            symbol = (
                str(row["symbol"])
                .strip()
                .upper()
            )

            key = (TARGET_DATE, symbol)

            if key in seen:
                continue

            new_rows.append(row.copy())
            seen.add(key)

    incoming = (
        pd.DataFrame(new_rows)
        if new_rows
        else pd.DataFrame()
    )

    if existing.empty and incoming.empty:
        combined = incoming
    elif existing.empty:
        combined = incoming
    elif incoming.empty:
        combined = existing
    else:
        combined = pd.concat(
            [existing, incoming],
            ignore_index=True,
        )

    if not combined.empty:
        combined["trading_date"] = (
            pd.to_datetime(
                combined["trading_date"],
                errors="coerce",
            )
            .dt.strftime("%Y-%m-%d")
        )

        combined["symbol"] = (
            combined["symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        combined = combined.drop_duplicates(
            subset=["trading_date", "symbol"],
            keep="first",
        )

        combined.to_csv(
            TARGET,
            index=False,
        )
    else:
        # Keep the expected schema if the layer is empty.
        combined.to_csv(
            TARGET,
            index=False,
        )

    day = combined[
        combined["trading_date"] == TARGET_DATE
    ].copy() if not combined.empty else pd.DataFrame()

    duplicate_keys = (
        int(
            day.duplicated(
                subset=["trading_date", "symbol"]
            ).sum()
        )
        if not day.empty
        else 0
    )

    print("--- FINAL 12-AUG VALIDATION ---")
    print("FILE:", TARGET)
    print("TOTAL ROWS:", len(combined))
    print("12-AUG ROWS:", len(day))
    print(
        "12-AUG UNIQUE SYMBOLS:",
        day["symbol"].nunique() if not day.empty else 0,
    )
    print("12-AUG DUPLICATE KEYS:", duplicate_keys)

    if not day.empty:
        cols = [
            c for c in [
                "trading_date",
                "observation_timestamp",
                "symbol",
                "direction",
                "approach_progress_pct",
                "approaching_level",
                "breakout_level",
            ]
            if c in day.columns
        ]
        print(day[cols].to_string(index=False))


if __name__ == "__main__":
    run()
