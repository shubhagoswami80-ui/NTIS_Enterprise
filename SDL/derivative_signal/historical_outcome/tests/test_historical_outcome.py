import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from historical_outcome.engine import HistoricalOutcomeEngine, OutcomeConfig
from historical_outcome.integration import build_historical_outcome_evidence


def test_forward_only_and_horizons():
    events = pd.DataFrame([{
        "symbol": "ABC",
        "event_timestamp": "2026-09-21 10:00:00",
        "event_price": 100.0,
        "direction": "BULLISH",
        "event": "VOLUME_SURGE",
    }])
    obs = pd.DataFrame([
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 09:59:00", "close": 99},
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 10:05:00", "close": 101},
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 10:15:00", "close": 103},
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 10:30:00", "close": 102},
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 11:00:00", "close": 105},
    ])
    out = HistoricalOutcomeEngine(OutcomeConfig(include_session_close=False, include_next_session=False)).evaluate(events, obs)
    assert set(out["outcome_window"]) == {"5m", "15m", "30m", "60m"}
    assert (out["observation_timestamp"] > pd.Timestamp("2026-09-21 10:00:00")).all()
    assert out.loc[out["outcome_window"] == "5m", "return_pct"].iloc[0] == 1.0


def test_directional_outcome_for_bearish():
    events = pd.DataFrame([{
        "symbol": "ABC",
        "event_timestamp": "2026-09-21 10:00:00",
        "event_price": 100.0,
        "direction": "BEARISH",
    }])
    obs = pd.DataFrame([
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 10:15:00", "close": 98},
    ])
    out = HistoricalOutcomeEngine(OutcomeConfig(intraday_horizons_minutes=(15,), include_session_close=False, include_next_session=False)).evaluate(events, obs)
    assert out["directional_outcome"].iloc[0] == "POSITIVE"


def test_next_session_btst_evidence():
    events = pd.DataFrame([{
        "symbol": "ABC",
        "event_timestamp": "2026-09-21 15:20:00",
        "event_price": 100.0,
        "direction": "BULLISH",
    }])
    obs = pd.DataFrame([
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 15:25:00", "close": 101},
        {"symbol": "ABC", "observation_timestamp": "2026-09-22 09:15:00", "close": 103},
    ])
    out = HistoricalOutcomeEngine(OutcomeConfig(intraday_horizons_minutes=(15,), include_session_close=True, include_next_session=True)).evaluate(events, obs)
    btst = out[out["outcome_window"] == "NEXT_SESSION_OPEN"]
    assert len(btst) == 1
    assert btst["outcome_type"].iloc[0] == "BTST_NEXT_SESSION"
    assert btst["return_pct"].iloc[0] == 3.0


def test_missing_future_observation_is_not_fabricated():
    events = pd.DataFrame([{
        "symbol": "ABC",
        "event_timestamp": "2026-09-21 14:00:00",
        "event_price": 100.0,
        "direction": "BULLISH",
    }])
    obs = pd.DataFrame([
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 14:02:00", "close": 101},
    ])
    out = HistoricalOutcomeEngine(OutcomeConfig(intraday_horizons_minutes=(15,), include_session_close=False, include_next_session=False)).evaluate(events, obs)
    assert out.empty


def test_integration_is_not_selection_gate():
    events = pd.DataFrame([{
        "symbol": "ABC",
        "event_timestamp": "2026-09-21 10:00:00",
        "event_price": 100.0,
        "direction": "BULLISH",
    }])
    obs = pd.DataFrame([
        {"symbol": "ABC", "observation_timestamp": "2026-09-21 10:05:00", "close": 101},
    ])
    result = build_historical_outcome_evidence(
        events, obs,
        OutcomeConfig(intraday_horizons_minutes=(5,), include_session_close=False, include_next_session=False)
    )
    assert result["is_selection_gate"] is False
    assert len(result["events"]) == 1
    assert len(result["outcomes"]) == 1
