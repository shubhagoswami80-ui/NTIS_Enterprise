from alert_chart.alert_rules import evaluate_rule
from alert_chart.examples import STRONG_CONFIRMATION_RULE, demo_context


def test_complex_rule_matches_on_crossing_and_event():
    result = evaluate_rule(STRONG_CONFIRMATION_RULE, demo_context())
    assert result.matched


def test_complex_rule_does_not_repeat_without_crossing():
    ctx = demo_context(previous_futures=10500, previous_pece=11000)
    assert not evaluate_rule(STRONG_CONFIRMATION_RULE, ctx).matched


def test_bearish_or_bullish_group():
    ctx = demo_context()
    ctx["current"]["direction"] = "BEARISH"
    assert evaluate_rule(STRONG_CONFIRMATION_RULE, ctx).matched
