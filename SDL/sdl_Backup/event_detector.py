from __future__ import annotations

import hashlib
import pandas as pd

def event_id(trading_date, symbol, observation_timestamp, strategy_version="SDL-P1-v1.0"):
    raw = f"{trading_date}|{symbol}|{observation_timestamp}|{strategy_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

def detect_first_crossings(current: pd.DataFrame, prior_events: pd.DataFrame | None, timestamp):
    prior_events = prior_events if prior_events is not None else pd.DataFrame()
    already = set()
    if not prior_events.empty and "trading_date" in prior_events.columns and "symbol" in prior_events.columns:
        already = set(
            zip(
                prior_events["trading_date"].astype(str),
                prior_events["symbol"].astype(str),
            )
        )

    events = []
    trading_date = pd.Timestamp(timestamp).date().isoformat()

    for _, row in current.iterrows():
        symbol = str(row.get("Symbol", "")).strip()
        if not symbol or not bool(row.get("above_breakout_level", False)):
            continue

        if (trading_date, symbol) in already:
            continue

        events.append({
            "event_id": event_id(trading_date, symbol, timestamp),
            "trading_date": trading_date,
            "observation_timestamp": pd.Timestamp(timestamp).isoformat(),
            "timestamp_precision": "snapshot",
            "symbol": symbol,
            "straddle_base_premium": row.get("straddle_base_premium"),
            "breakout_level": row.get("breakout_level"),
            "current_straddle_premium": row.get("derived_straddle_premium"),
            "atm_straddle_pct": row.get("atm_straddle_pct"),
            "stock_open": row.get("daily_open_reference"),
            "current_price": row.get("Close"),
            "price_chg_pct": row.get("Price Chg %"),
            "iv_chg_pct": row.get("IV Chg %"),
            "oi_chg_pct": row.get("OI Chg %"),
            "pcr_chg_pct": row.get("PCR Chg %"),
            "ce_oi_chg_pct": row.get("Tot CE OI Chg %"),
            "pe_oi_chg_pct": row.get("Tot PE OI Chg %"),
            "pe_minus_ce_oi_chg": row.get("Tot PE-CE OI Chg"),
            "strategy_version": "SDL-P1-v1.2",
            "processing_status": "VALID_BREAKOUT",
        })

    return pd.DataFrame(events)
