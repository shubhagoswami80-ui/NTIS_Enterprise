from alert_chart.chart_datafeed import build_series


def test_chart_series_is_bounded_and_sorted():
    rows = [
        {"symbol": "ABC", "observation_timestamp": "2026-09-20T10:02:00", "current_price": 102},
        {"symbol": "ABC", "observation_timestamp": "2026-09-20T10:01:00", "current_price": 101},
        {"symbol": "XYZ", "observation_timestamp": "2026-09-20T10:00:00", "current_price": 1},
    ]
    out = build_series(rows, "ABC", limit=2)
    assert [x["value"] for x in out] == [101.0, 102.0]
