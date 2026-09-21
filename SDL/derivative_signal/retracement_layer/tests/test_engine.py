from retracement_layer.engine import RetracementEngine


def row(ts, price, direction="BULLISH", r3=100.0, **extra):
    return {
        "symbol": "ABC", "observation_timestamp": ts,
        "reference_price": price, "direction": direction,
        "decision_direction": direction, "camarilla_r3": r3,
        "camarilla_s3": 90.0, **extra,
    }


def test_bullish_watch_reentry_one_shot():
    e = RetracementEngine()
    assert e.process(row("t1", 101))["interaction"] == "ACTIVE"
    assert e.process(row("t2", 99.5))["interaction"] == "WATCH"
    assert e.process(row("t3", 100.5))["interaction"] == "RE-ENTRY ALERT"
    assert e.process(row("t4", 101))["interaction"] == "NO_ACTION"


def test_opposite_direction_is_terminal():
    e = RetracementEngine()
    e.process(row("t1", 101))
    out = e.process(row("t2", 98, direction="BEARISH"))
    assert out["lifecycle"] == "REVERSAL"


def test_ema_vwap_rsi_are_evidence_only():
    e = RetracementEngine()
    out = e.process(row("t1", 101, ema20=100, vwap=99.5, rsi_5m=72, rsi_15m=68))
    assert out["ema20"] == 100
    assert out["vwap"] == 99.5
    assert out["rsi_5m"] == 72
    assert out["rsi_15m"] == 68
