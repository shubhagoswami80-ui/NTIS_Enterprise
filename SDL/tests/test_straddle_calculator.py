import pandas as pd
from straddle_calculator import derive_current_straddle_premium, add_breakout_level

def test_fixed_daily_open_reference():
    df = pd.DataFrame({"Symbol":["TEST"],"ATM Straddle %":[5.0],"Open":[1000.0],"Close":[1100.0]})
    out = derive_current_straddle_premium(df)
    assert out.loc[0,"daily_open_reference"] == 1000.0
    assert out.loc[0,"derived_straddle_premium"] == 50.0

def test_close_does_not_change_straddle_reference():
    df = pd.DataFrame({"Symbol":["TEST"],"ATM Straddle %":[5.0],"Open":[1000.0],"Close":[1200.0]})
    out = derive_current_straddle_premium(df)
    assert out.loc[0,"derived_straddle_premium"] == 50.0

def test_breakout_is_strictly_greater_than_20_percent():
    df = pd.DataFrame({
        "Symbol":["TEST","TEST2"], "ATM Straddle %":[4.8,4.801], "Open":[1000.0,1000.0]
    })
    out = derive_current_straddle_premium(df)
    out = add_breakout_level(out, {"TEST":40.0,"TEST2":40.0}, 1.20)
    assert bool(out.loc[0,"above_breakout_level"]) is False
    assert bool(out.loc[1,"above_breakout_level"]) is True

