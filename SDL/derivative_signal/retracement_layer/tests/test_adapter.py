from retracement_layer.adapter import is_prequalified, process_qualified_pool
from retracement_layer.engine import RetracementEngine


def test_adapter_does_not_rank():
    assert is_prequalified({"decision_state": "ACTIVE_BULLISH"})
    assert not is_prequalified({"decision_state": "NO DECISION"})


def test_engine_errors_are_contained_per_row():
    engine = RetracementEngine()
    rows = [{"decision_state": "ACTIVE_BULLISH", "symbol": "ABC", "observation_timestamp": "t", "reference_price": 101, "direction": "BULLISH", "camarilla_r3": 100}]
    out = process_qualified_pool(engine, rows)
    assert len(out) == 1
