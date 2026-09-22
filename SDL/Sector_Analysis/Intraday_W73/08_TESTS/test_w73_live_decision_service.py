from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "02_FEATURE_ENGINE"))
sys.path.insert(0, str(ROOT / "06_ALERTS"))

from w73_live_decision_service import decision_summary, evaluate_latest_maturity, matured_cuts


def _row(ts, close, chg, *, family="FUTURES", fut_oi=100, fut_pct=2.0):
    return {
        "Symbol": "TEST",
        "_observation_timestamp": ts.isoformat(timespec="seconds"),
        "Open": close - 1,
        "High": close + 1,
        "Low": close - 2,
        "Close": close,
        "Price Chg": chg,
        "Price Chg %": chg / 100.0,
        "Volume Chg (%)": 10.0,
        "Tot CE OI Chg": 100.0,
        "Tot PE OI Chg": 120.0,
        "Tot PE-CE OI Chg": 20.0,
        "Tot CE OI Chg %": 2.0,
        "Tot PE OI Chg %": 2.5,
        "Tot PE-CE OI Chg %": 0.5,
        "OI Chg": fut_oi,
        "OI Chg %": fut_pct,
        "Buildup": "LB",
        "family": family,
    }


def test_maturity_cuts_are_causal():
    asof = datetime(2026, 9, 18, 9, 52)
    assert matured_cuts(asof) == ["09:30", "09:45"]


def test_future_rows_are_not_admitted_to_latest_maturity():
    base = datetime(2026, 9, 18, 9, 15)
    rows = []
    for i in range(5):
        rows.append(_row(base + timedelta(minutes=5 * i), 100 - i, -1))
    # This row is after 09:45 and must not enter the 09:45 decision.
    rows.append(_row(datetime(2026, 9, 18, 9, 50), 120, 20))
    asof, maturity, decisions = evaluate_latest_maturity(rows, trading_date="2026-09-18")
    assert maturity == "09:45"
    assert decisions and decisions[0].observation_timestamp <= "2026-09-18T09:45:00"


def test_summary_is_explicit_and_fail_closed():
    rows = []
    asof, maturity, decisions = evaluate_latest_maturity(rows, trading_date="2026-09-18")
    assert decisions == []
    assert decision_summary(decisions) == {"QUALIFIED": 0, "WAIT": 0, "NOT_READY": 0}
