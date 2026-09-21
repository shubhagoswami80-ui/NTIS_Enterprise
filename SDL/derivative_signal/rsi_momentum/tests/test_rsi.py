import pandas as pd

from rsi_momentum.engine import RSIEngine, wilder_rsi
from rsi_momentum.integration import build_rsi_evidence


def history(n=60):
    base = pd.Timestamp("2026-09-21 09:15")
    return [
        {"source_timestamp": base + pd.Timedelta(minutes=15*i), "Close": 100.0 + i}
        for i in range(n)
    ]


def test_wilder_rsi_uptrend_reaches_100():
    s = pd.Series(range(1, 17), dtype=float)
    assert wilder_rsi(s, 14) == 100.0


def test_point_in_time_excludes_future_observation():
    h = history(70)
    current = pd.Timestamp("2026-09-21 12:00")
    engine = RSIEngine()
    a = engine.calculate(h, current)
    h2 = h + [{"source_timestamp": pd.Timestamp("2026-09-21 15:30"), "Close": 1.0}]
    b = engine.calculate(h2, current)
    assert a == b


def test_same_day_session_only():
    h = history(60)
    h.insert(0, {"source_timestamp": pd.Timestamp("2026-09-20 15:30"), "Close": 1.0})
    result = RSIEngine().calculate(h, pd.Timestamp("2026-09-21 14:00"))
    assert result.observation_count == 20


def test_mtf_evidence_is_non_gate_and_has_state():
    evidence = build_rsi_evidence(history(80), pd.Timestamp("2026-09-21 15:00"))
    assert evidence["rsi_15m"] is not None
    assert evidence["rsi_momentum_state"] in {"STRONG / EXTENDED", "POSITIVE", "NEGATIVE", "WEAK / EXTENDED", "WARMING UP"}
    assert "decision_state" not in evidence


def test_warmup_is_explicit():
    result = RSIEngine().calculate(history(5), pd.Timestamp("2026-09-21 10:30"))
    assert result.rsi_15m is None
