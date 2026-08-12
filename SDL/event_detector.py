from __future__ import annotations

import hashlib

import pandas as pd

from config import STRATEGY_VERSION


def event_id(
    trading_date,
    symbol,
    observation_timestamp,
    strategy_version=STRATEGY_VERSION,
):
    raw = (
        f"{trading_date}|{symbol}|"
        f"{observation_timestamp}|{strategy_version}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def detect_first_crossings(
    current: pd.DataFrame,
    prior_events: pd.DataFrame | None,
    timestamp,
):
    """
    Preserve existing daily events and append only a symbol's
    first valid breakout for that trading day.
    """

    prior_events = (
        prior_events
        if prior_events is not None
        else pd.DataFrame()
    )

    already = set()

    if (
        not prior_events.empty
        and "trading_date" in prior_events.columns
        and "symbol" in prior_events.columns
    ):
        already = set(
            zip(
                prior_events["trading_date"].astype(str),
                prior_events["symbol"].astype(str),
            )
        )

    trading_date = pd.Timestamp(timestamp).date().isoformat()
    events = []

    for _, row in current.iterrows():
        symbol = str(row.get("Symbol", "")).strip()

        if not symbol:
            continue

        if not bool(row.get("standard_straddle_breakout", False)):
            continue

        if (trading_date, symbol) in already:
            continue

        direction = str(row.get("breakout_direction", "NONE"))
        expected_price = (
            row.get("upper_straddle_breakout_level")
            if direction == "UP"
            else row.get("lower_straddle_breakout_level")
        )

        current_price = row.get("current_price")
        breakout_distance = pd.NA

        if pd.notna(current_price) and pd.notna(expected_price):
            breakout_distance = (
                current_price - expected_price
                if direction == "UP"
                else expected_price - current_price
            )

        events.append({
            "event_id": event_id(
                trading_date,
                symbol,
                timestamp,
            ),
            "trading_date": trading_date,
            "observation_timestamp": pd.Timestamp(
                timestamp
            ).isoformat(),
            "symbol": symbol,
            "direction": direction,
            "status": "VALID_BREAKOUT",

            # Dashboard-facing
            "open_price": row.get("daily_open_reference"),
            "current_price": current_price,
            "expected_1x_price": expected_price,
            "expected_1x_move": row.get(
                "opening_straddle_premium"
            ),
            "breakout_distance": breakout_distance,
            "price_chg_pct": row.get("Price Chg %"),

            # Required evidence
            "high": row.get("High"),
            "low": row.get("Low"),
            "atm_straddle_pct": row.get("atm_straddle_pct"),
            "opening_straddle_premium": row.get(
                "opening_straddle_premium"
            ),
            "source_atm_straddle_price": row.get(
                "source_atm_straddle_price"
            ),

            # Future replay context
            "iv_chg_pct": row.get("IV Chg %"),
            "oi_chg_pct": row.get("OI Chg %"),
            "pcr_chg_pct": row.get("PCR Chg %"),
            "ce_oi_chg_pct": row.get("Tot CE OI Chg %"),
            "pe_oi_chg_pct": row.get("Tot PE OI Chg %"),
            "pe_minus_ce_oi_chg": row.get(
                "Tot PE-CE OI Chg"
            ),
            "strategy_version": STRATEGY_VERSION,
        })

    return pd.DataFrame(events)
