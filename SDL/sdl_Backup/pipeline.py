from __future__ import annotations
from pathlib import Path
import pandas as pd

from config import BREAKOUT_MULTIPLIER, EVENT_CSV, STATE_JSON, ensure_runtime_directories
from sdl.source_loader import load_primary_snapshot
from sdl.straddle_calculator import derive_current_straddle_premium, add_breakout_level
from sdl.event_detector import detect_first_crossings
from sdl.storage import load_events, append_events, load_state, save_state

def _numeric(value):
    return pd.to_numeric(str(value).replace(",", ""), errors="coerce")

def build_or_load_daily_base(df: pd.DataFrame, trading_date: str, state: dict) -> dict:
    bases = state.setdefault("daily_base_premiums", {})
    day_bases = bases.setdefault(trading_date, {})
    for _, row in df.iterrows():
        symbol = str(row.get("Symbol", "")).strip()
        if not symbol or symbol in day_bases:
            continue
        daily_open = _numeric(row.get("Open"))
        atm_pct = _numeric(row.get("ATM Straddle %"))
        if pd.notna(daily_open) and pd.notna(atm_pct):
            day_bases[symbol] = float(daily_open * atm_pct / 100.0)
    return day_bases

def process_snapshot(path: Path, timestamp=None):
    ensure_runtime_directories()
    df, observed_at = load_primary_snapshot(path, timestamp)
    df = derive_current_straddle_premium(df)

    state = load_state(STATE_JSON)
    trading_date = observed_at.date().isoformat()
    base_map = build_or_load_daily_base(df, trading_date, state)
    df = add_breakout_level(df, base_map, BREAKOUT_MULTIPLIER)

    prior = load_events(EVENT_CSV)
    events = detect_first_crossings(df, prior, observed_at)
    append_events(events, EVENT_CSV)

    state.update({
        "last_source_file": str(path),
        "last_observation_timestamp": observed_at.isoformat(),
        "last_event_count": int(len(events)),
        "strategy_version": "SDL-P1-v1.2",
        "breakout_rule": "current_straddle > frozen_daily_base_straddle * 1.20",
        "daily_open_is_fixed_reference": True,
    })
    save_state(state, STATE_JSON)
    return events, df, observed_at
