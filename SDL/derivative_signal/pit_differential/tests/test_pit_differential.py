import pandas as pd

from pit_differential import DifferentialConfig, PITDifferentialEngine


def _frame():
    rows = []
    for day, mult in [
        ("2026-09-10", 1.0),
        ("2026-09-11", 1.1),
        ("2026-09-14", 1.2),
        ("2026-09-15", 1.0),
        ("2026-09-16", 1.1),
        ("2026-09-17", 1.0),
        ("2026-09-18", 5.0),
    ]:
        rows.append({
            "trading_date": day,
            "observation_timestamp": f"{day} 10:00:00",
            "symbol": "ABC",
            "Volume": 100 * mult,
            "Fut OI Chg %": 2 * mult,
            "Fut Buildup": "SC",
            "CE OI Chg %": 3 * mult,
            "PE OI Chg %": 4 * mult,
        })
    return pd.DataFrame(rows)


def test_point_in_time_uses_only_prior_sessions():
    r = PITDifferentialEngine(DifferentialConfig(horizons=(2, 3, 4, 5))).analyze(
        _frame(), "2026-09-18 10:00:00"
    ).rows
    assert not r.empty
    assert r["historical_sessions"].max() <= 4


def test_unusual_event_detected():
    r = PITDifferentialEngine(
        DifferentialConfig(horizons=(2,), ratio_threshold=2.0)
    ).analyze(_frame(), "2026-09-18 10:00:00").rows
    volume = r[r["event"].eq("VOLUME_SURGE")]
    assert not volume.empty
    assert volume["unusual"].any()


def test_no_future_session_is_used():
    f = _frame()
    engine = PITDifferentialEngine(DifferentialConfig(horizons=(2,)))
    baseline = engine.analyze(f, "2026-09-18 10:00:00").rows

    f.loc[len(f)] = {
        "trading_date": "2026-09-19",
        "observation_timestamp": "2026-09-19 10:00:00",
        "symbol": "ABC",
        "Volume": 999999,
        "Fut OI Chg %": 99,
        "Fut Buildup": "SC",
        "CE OI Chg %": 99,
        "PE OI Chg %": 99,
    }
    with_future = engine.analyze(f, "2026-09-18 10:00:00").rows

    # The later session must not change the PIT evidence for 18-Sep.
    cols = ["event", "historical_median", "historical_sessions", "horizon_days"]
    left = baseline[cols].sort_values(cols).reset_index(drop=True)
    right = with_future[cols].sort_values(cols).reset_index(drop=True)
    assert left.equals(right)


def test_missing_metric_is_reported_not_fatal():
    f = _frame().drop(columns=["CE OI Chg %"])
    result = PITDifferentialEngine(DifferentialConfig(horizons=(2,))).analyze(
        f, "2026-09-18 10:00:00"
    )
    assert "ce_oi_chg_pct" in result.missing_metrics
    assert not result.rows.empty


def test_differential_is_not_a_selection_gate():
    from pit_differential.integration import build_differential_evidence
    e = build_differential_evidence(_frame(), "2026-09-18 10:00:00")
    assert e["is_selection_gate"] is False
    assert "unusual_symbols" in e
