from stock_state import build_stock_state_evidence, compose_stock_state


def test_composes_independent_layers_without_filtering():
    row = {"symbol": "ABC", "sdl_state": "QUALIFIED"}
    r = {"lifecycle": "WATCH", "alert_type": None}
    m = {"rsi_15m": 62, "rsi_30m": 58, "rsi_1h": 55, "rsi_2h": 53, "mtf_alignment": "BULLISH", "momentum_state": "POSITIVE"}
    state = compose_stock_state(row, retracement=r, rsi=m)
    assert state.symbol == "ABC"
    assert state.sdl_state == "QUALIFIED"
    assert state.retracement_state == "WATCH"
    assert state.rsi_15m == 62.0
    assert state.state == "RETRACEMENT WATCH"


def test_missing_layer_is_preserved_as_missing():
    state = compose_stock_state({"symbol": "XYZ", "sdl_state": "QUALIFIED"})
    assert state.retracement_state is None
    assert state.rsi_15m is None
    assert state.state == "QUALIFIED"


def test_reversal_has_descriptive_precedence_only():
    state = compose_stock_state(
        {"symbol": "XYZ", "sdl_state": "QUALIFIED"},
        retracement={"lifecycle": "REVERSAL"},
        rsi={"momentum_state": "POSITIVE"},
    )
    assert state.state == "REVERSAL"


def test_reentry_alert_is_exposed():
    state = compose_stock_state(
        {"symbol": "XYZ", "sdl_state": "QUALIFIED"},
        retracement={"lifecycle": "WATCH", "alert_type": "RE-ENTRY ALERT"},
    )
    assert state.reentry_state == "RE-ENTRY ALERT"
    assert state.state == "RE-ENTRY ALERT"


def test_integration_keeps_all_input_rows():
    rows = [{"symbol": "A", "sdl_state": "QUALIFIED"}, {"symbol": "B", "sdl_state": "OTHER"}]
    out = build_stock_state_evidence(rows)
    assert [x["symbol"] for x in out] == ["A", "B"]
    assert len(out) == 2
