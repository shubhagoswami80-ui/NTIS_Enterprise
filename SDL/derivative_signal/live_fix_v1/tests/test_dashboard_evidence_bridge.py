from __future__ import annotations

import pandas as pd

from dashboard_evidence_bridge import build_live_evidence


def _result():
    return pd.DataFrame([{
        "symbol": "TEST",
        "decision_state": "ACTIVE_BULLISH",
        "decision_direction": "BULLISH",
        "observation_timestamp": "2026-09-22 10:00:00",
        "Close": 100.0,
    }])


def test_bridge_is_additive_and_sdl_owned():
    package = build_live_evidence(
        result=_result(),
        trading_date="2026-09-22",
        observation_timestamp="2026-09-22 10:00:00",
        history_by_symbol={
            "TEST": [
                {"symbol":"TEST","observation_timestamp":f"2026-09-22 09:{m:02d}:00","Close":100+m/10}
                for m in range(15, 61, 5)
            ]
        },
    )
    assert package["selection_gate"] is False
    assert package["decision_owner"] == "SDL"
    assert list(package["evidence"]["sdl"]["symbol"]) == ["TEST"]


def test_authoritative_timestamp_and_missing_layers_are_safe():
    package = build_live_evidence(
        result=_result(),
        trading_date="2026-09-22",
        observation_timestamp="2026-09-22 10:00:00",
    )
    assert package["observation_timestamp"] == "2026-09-22 10:00:00"
    assert package["evidence"]["pit_differential"].empty
    assert package["evidence"]["historical_outcome"].empty
    assert package["evidence"]["pdna"].empty


def test_pit_is_point_in_time_and_not_a_gate():
    pit = pd.DataFrame([
        {"trading_date":"2026-09-20","observation_timestamp":"2026-09-20 10:00:00","symbol":"TEST","volume":10},
        {"trading_date":"2026-09-21","observation_timestamp":"2026-09-21 10:00:00","symbol":"TEST","volume":12},
        {"trading_date":"2026-09-22","observation_timestamp":"2026-09-22 10:00:00","symbol":"TEST","volume":30},
    ])
    package = build_live_evidence(
        result=_result(),
        trading_date="2026-09-22",
        observation_timestamp="2026-09-22 10:00:00",
        pit_history=pit,
    )
    assert package["selection_gate"] is False
    rows = package["evidence"]["pit_differential"]
    assert rows.empty or rows["current_timestamp"].eq(pd.Timestamp("2026-09-22 10:00:00")).all()


def test_alert_failure_cannot_break_sdl():
    def fail_context(*args, **kwargs):
        raise RuntimeError("synthetic alert failure")

    package = build_live_evidence(
        result=_result(),
        trading_date="2026-09-22",
        observation_timestamp="2026-09-22 10:00:00",
        alert_rules=[{"rule_id":"R1"}],
        alert_build_context=fail_context,
        alert_evaluate_snapshot=lambda *a, **k: [],
    )
    assert package["evidence"]["alerts"].empty
    assert not package["evidence"]["sdl"].empty
