import pandas as pd
from retracement_runtime.integration import enrich_snapshot


def history(n=60):
    base = pd.Timestamp("2026-09-23 09:15")
    return [{"source_timestamp": base + pd.Timedelta(minutes=15*i), "Close": 100.0+i, "Volume": 1000+i} for i in range(n)]


def test_rsi_and_stock_state_are_built_without_filtering():
    frame = pd.DataFrame([{
        "symbol": "ABC", "decision_state": "ACTIVE_BULLISH",
        "decision_direction": "BULLISH", "observation_timestamp": "2026-09-23 15:00:00"
    }])
    out, state = enrich_snapshot(frame, history_by_symbol={"ABC": history()})
    assert len(out) == 1
    assert not state.empty
    assert out.iloc[0]["rsi_15m"] is not None
    assert out.iloc[0]["stock_state"] is not None


def test_future_observations_are_not_used():
    h = history()
    frame = pd.DataFrame([{
        "symbol": "ABC", "decision_state": "ACTIVE_BULLISH",
        "decision_direction": "BULLISH", "observation_timestamp": "2026-09-23 12:00:00"
    }])
    a, _ = enrich_snapshot(frame, history_by_symbol={"ABC": h})
    h2 = h + [{"source_timestamp": pd.Timestamp("2026-09-23 15:30"), "Close": 1.0, "Volume": 1000}]
    b, _ = enrich_snapshot(frame, history_by_symbol={"ABC": h2})
    assert a.iloc[0]["rsi_15m"] == b.iloc[0]["rsi_15m"]
