import pandas as pd
from event_detector import detect_first_crossings

def test_first_crossing():
    current = pd.DataFrame([{
        "Symbol": "TEST",
        "above_breakout_level": True,
        "straddle_base_premium": 40.0,
        "breakout_level": 48.0,
        "derived_straddle_premium": 49.0,
        "atm_straddle_pct": 4.9,
        "stock_open": 1000.0,
        "Close": 1010.0,
        "Price Chg %": 1.0,
        "IV Chg %": 2.0,
        "OI Chg %": 3.0,
        "PCR Chg %": 1.0,
        "Tot CE OI Chg %": 2.0,
        "Tot PE OI Chg %": 4.0,
        "Tot PE-CE OI Chg": 10.0,
    }])
    events = detect_first_crossings(current, pd.DataFrame(), "2026-08-11 10:00")
    assert len(events) == 1
    assert events.iloc[0]["symbol"] == "TEST"

