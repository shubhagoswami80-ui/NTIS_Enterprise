from retracement_layer.integration import RetracementIntegration


def qualified(ts, price, direction="BULLISH"):
    return {
        "symbol": "ABC",
        "observation_timestamp": ts,
        "reference_price": price,
        "direction": direction,
        "decision_direction": direction,
        "decision_state": "ACTIVE_BULLISH" if direction == "BULLISH" else "ACTIVE_BEARISH",
        "camarilla_r3": 100.0,
        "camarilla_s3": 90.0,
    }


def test_integration_uses_only_qualified_pool():
    bridge = RetracementIntegration()
    out = bridge.process_qualified_rows([
        qualified("t1", 101),
        {**qualified("t1", 101), "symbol": "NOPE", "decision_state": "NO DECISION"},
    ])
    assert [row["symbol"] for row in out] == ["ABC"]


def test_integration_state_round_trip():
    first = RetracementIntegration()
    first.process_qualified_rows([qualified("t1", 101)])
    saved = first.snapshot()

    second = RetracementIntegration(saved)
    out = second.process_qualified_rows([qualified("t2", 99.5)])
    assert out[0]["interaction"] == "WATCH"


def test_integration_keeps_engine_errors_contained():
    bridge = RetracementIntegration()
    original = bridge.engine.process

    def failing(row):
        if row.get("symbol") == "BAD":
            raise RuntimeError("synthetic engine failure")
        return original(row)

    bridge.engine.process = failing
    out = bridge.process_qualified_rows([
        {**qualified("t1", 101), "symbol": "GOOD"},
        {**qualified("t1", 101), "symbol": "BAD"},
    ])
    assert len(out) == 2
    assert out[1]["lifecycle"] == "ENGINE_ERROR"
