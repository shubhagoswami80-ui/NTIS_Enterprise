from datetime import datetime

from w73_exact_v8_live_engine import (
    V8_COLUMNS,
    MATURITY_CUTS,
    _prepare_canonical_history,
    build_exact_v8,
)

def raw(ts, symbol="AAA", price=-1.0):
    return {
        "Symbol": symbol,
        "_observation_timestamp": ts,
        "Open": 100, "High": 101, "Low": 99, "Close": 100,
        "Price Chg": price,
        "Price Chg %": price,
        "Volume Chg (%)": 100,
        "Tot CE OI Chg": 10,
        "Tot PE OI Chg": 20,
        "Tot PE-CE OI Chg": -5,
        "Tot CE OI Chg %": 1,
        "Tot PE OI Chg %": 1,
        "Tot PE-CE OI Chg %": -1,
        "OI Chg": None,
        "OI Chg %": None,
        "Buildup": "LB",
        "IV Chg": 1,
        "IV Chg %": 1,
        "PCR Chg": 1,
        "PCR Chg %": 1,
        "ATM Straddle Price": 10,
        "ATM Straddle %": 1,
        "family": "OPTIONS",
    }

def test_exact_v8_vocabulary_is_25():
    assert len(V8_COLUMNS) == 25
    assert set(MATURITY_CUTS) == {"09:30", "09:45", "10:00", "10:15"}

def test_missing_futures_fields_fail_closed():
    rows = [
        raw("2026-09-18T09:18:09"),
        raw("2026-09-18T09:23:20"),
        raw("2026-09-18T09:28:29"),
        raw("2026-09-18T09:33:41"),
    ]
    out = build_exact_v8(rows, symbol="AAA", trading_date="2026-09-18", maturity="09:30", orb_minutes=10)
    assert out.status == "NOT_READY"
    assert "fut_dir" in out.missing_fields or "fut_oi_state" in out.missing_fields
    assert out.variants["W73-A"] is False
    assert out.variants["W73-B"] is False

def test_future_rows_cannot_change_maturity_vector():
    rows = [
        raw("2026-09-18T09:18:09", price=-1),
        raw("2026-09-18T09:23:20", price=-1),
        raw("2026-09-18T09:28:29", price=-1),
        raw("2026-09-18T09:33:41", price=50),
        raw("2026-09-18T09:45:00", price=50),
    ]
    out = build_exact_v8(rows, symbol="AAA", trading_date="2026-09-18", maturity="09:30", orb_minutes=10)
    assert out.observation_timestamp == "2026-09-18T09:28:29"
