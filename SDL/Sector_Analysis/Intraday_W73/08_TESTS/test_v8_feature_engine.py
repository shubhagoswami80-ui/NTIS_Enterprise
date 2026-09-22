from datetime import datetime

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "02_FEATURE_ENGINE"))

from v8_feature_engine import V8FeatureEngine, V8_FEATURE_COLUMNS


def base_snapshot():
    return {c: "X" for c in V8_FEATURE_COLUMNS}


def test_missing_never_matches():
    e = V8FeatureEngine()
    s = base_snapshot()
    s["orb_agree"] = "NO"
    s["magnitude_count_band"] = 0
    s["px_all_negative_pre_maturity"] = True
    out = e.match(s)
    assert out["W73-A"] is False
    assert out["W73-B"] is False


def test_variant_a_exact_match():
    e = V8FeatureEngine()
    s = base_snapshot()
    s["orb_agree"] = "NO"
    s["magnitude_count_band"] = 0
    s["px_all_negative_pre_maturity"] = True
    s = e.build(s)
    assert e.match(s)["W73-A"] is True
    assert e.match(s)["W73-B"] is False


def test_variant_b_exact_match():
    e = V8FeatureEngine()
    s = base_snapshot()
    s["orb_price_agree"] = "NO"
    s["magnitude_count_band"] = 0
    s["px_all_negative_pre_maturity"] = True
    s = e.build(s)
    assert e.match(s)["W73-A"] is False
    assert e.match(s)["W73-B"] is True


def test_trajectory_is_pre_maturity_only():
    e = V8FeatureEngine()
    maturity = datetime(2026, 9, 18, 10, 0)
    rows = [
        {"timestamp": "2026-09-18T09:35:00", "price_chg_pct": -0.20},
        {"timestamp": "2026-09-18T09:45:00", "price_chg_pct": -0.10},
        {"timestamp": "2026-09-18T10:00:00", "price_chg_pct": 0.50},
        {"timestamp": "2026-09-18T10:05:00", "price_chg_pct": 1.00},
    ]
    t = e.derive_trajectory(rows, maturity_timestamp=maturity)
    assert t.px_all_negative_pre_maturity is True
    assert t.px_negative_count_pre_maturity == 2
    assert t.observations_used == 2


def test_missing_trajectory_is_not_false():
    e = V8FeatureEngine()
    t = e.derive_trajectory([], maturity_timestamp=datetime(2026, 9, 18, 10, 0))
    assert t.px_all_negative_pre_maturity is None
    assert t.px_negative_count_pre_maturity is None
