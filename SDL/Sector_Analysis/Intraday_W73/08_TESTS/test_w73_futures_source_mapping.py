from w73_exact_v8_live_engine import canonicalize_row

def test_daywise_default_family_is_futures():
    row = {
        "Symbol": "HDFCBANK",
        "_observation_timestamp": "2026-09-18T09:18:09",
        "Open": 717.5, "High": 720.25, "Low": 716.7, "Close": 719.0,
        "OI Chg": 100, "OI Chg %": 2.0, "Buildup": "LB",
    }
    out = canonicalize_row(row)
    assert out["family"] == "FUTURES"
    assert out["fut_num"] == 100
    assert out["fut_pct"] == 2.0
