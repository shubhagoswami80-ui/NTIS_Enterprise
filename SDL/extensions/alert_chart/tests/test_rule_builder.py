from alert_chart.alert_rule_builder import _condition_default, _field_items


def test_field_items_and_defaults():
    items = _field_items()
    keys = [x[0] for x in items]
    assert "futures.oi_change" in keys
    assert "options.pe_ce_oi_change" in keys
    assert _condition_default("futures.oi_change")["value"] == 0
    assert _condition_default("event.first_alert")["value"] is False
