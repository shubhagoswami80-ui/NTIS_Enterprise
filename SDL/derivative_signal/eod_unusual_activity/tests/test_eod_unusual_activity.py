import pandas as pd

from eod_unusual_activity.engine import (
    available_filter_values,
    current_unusual_activity,
    current_unusual_symbols,
    filter_current_unusual,
)
from eod_unusual_activity.integration import build_eod_unusual_activity


def sample():
    return pd.DataFrame([
        {"symbol":"AAA","event":"VOLUME_SURGE","current_timestamp":"2026-09-18 15:30:00",
         "current_value":300,"current_magnitude":300,"historical_median":100,
         "current_vs_median_ratio":3.0,"robust_z":2.5,"historical_sessions":5,
         "horizon_days":5,"unusual":True},
        {"symbol":"BBB","event":"PE_OI_BUILDUP","current_timestamp":"2026-09-18 15:30:00",
         "current_value":110,"current_magnitude":110,"historical_median":100,
         "current_vs_median_ratio":1.1,"robust_z":0.5,"historical_sessions":5,
         "horizon_days":5,"unusual":False},
        {"symbol":"AAA","event":"VOLUME_SURGE","current_timestamp":"2026-09-18 15:25:00",
         "current_value":250,"current_magnitude":250,"historical_median":100,
         "current_vs_median_ratio":2.5,"robust_z":2.1,"historical_sessions":5,
         "horizon_days":5,"unusual":True},
        {"symbol":"CCC","event":"FUTURES_SHORT_COVERING","current_timestamp":"2026-09-18 15:30:00",
         "current_value":250,"current_magnitude":250,"historical_median":100,
         "current_vs_median_ratio":2.5,"robust_z":2.2,"historical_sessions":4,
         "horizon_days":10,"unusual":True},
    ])


def test_latest_point_in_time_only():
    out = current_unusual_activity(sample())
    assert set(out["symbol"]) == {"AAA", "CCC"}
    assert out["current_timestamp"].nunique() == 1
    assert out["current_timestamp"].iloc[0].strftime("%H:%M:%S") == "15:30:00"


def test_dynamic_filter_values():
    values = available_filter_values(current_unusual_activity(sample()))
    assert values["event"] == ["FUTURES_SHORT_COVERING", "VOLUME_SURGE"]
    assert sorted(values["horizon_days"]) == [5, 10]
    assert values["symbol"] == ["AAA", "CCC"]


def test_filters_are_display_only():
    out = filter_current_unusual(sample(), events=["VOLUME_SURGE"], min_ratio=2.8)
    assert list(out["symbol"]) == ["AAA"]
    assert out.iloc[0]["current_vs_median_ratio"] == 3.0


def test_symbols_are_current_unusual_only():
    assert current_unusual_symbols(sample()) == ["AAA", "CCC"]


def test_integration_preserves_selection_gate_boundary():
    result = build_eod_unusual_activity(sample(), horizons=[10])
    assert result["is_selection_gate"] is False
    assert list(result["rows"]["symbol"]) == ["CCC"]
    assert set(result["unfiltered_current_unusual"]["symbol"]) == {"AAA", "CCC"}
