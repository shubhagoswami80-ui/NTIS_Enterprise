from __future__ import annotations

from typing import Any

from .alert_rules import validate_rule


def rule_template(name: str = "New Alert") -> dict[str, Any]:
    return {
        "id": "rule-new",
        "name": name,
        "enabled": True,
        "priority": 50,
        "rearm": {"mode": "ON_CROSSING", "cooldown_seconds": 0},
        "root": {"type": "group", "operator": "ALL", "children": []},
    }


def add_condition(rule: dict[str, Any], condition: dict[str, Any]) -> dict[str, Any]:
    validate_condition(condition)
    rule["root"].setdefault("children", []).append(condition)
    return rule


def validate_condition(condition: dict[str, Any]) -> None:
    if condition.get("type", "condition") != "condition":
        raise ValueError("Condition node type must be 'condition'")
    if not condition.get("field") or not condition.get("operator"):
        raise ValueError("Condition requires field and operator")


# UI-ready presets. They are examples, not active alerts.
PRESETS = {
    "Strong Futures + PE/CE + Breakout": {
        "type": "group", "operator": "ALL", "children": [
            {"type": "condition", "field": "futures.oi_change", "operator": "CROSSED_ABOVE", "value": 10000},
            {"type": "condition", "field": "options.pe_ce_oi_change", "operator": "CROSSED_ABOVE", "value": 10000},
            {"type": "condition", "field": "strength.label", "operator": "=", "value": "STRONG"},
            {"type": "group", "operator": "ANY", "children": [
                {"type": "condition", "field": "direction", "operator": "=", "value": "BULLISH"},
                {"type": "condition", "field": "direction", "operator": "=", "value": "BEARISH"},
            ]},
            {"type": "group", "operator": "ANY", "children": [
                {"type": "condition", "field": "event.breakout", "operator": "=", "value": True},
                {"type": "condition", "field": "event.first_alert", "operator": "=", "value": True},
            ]},
        ]
    },
    "Strong First Alert": {
        "type": "group", "operator": "ALL", "children": [
            {"type": "condition", "field": "event.first_alert", "operator": "=", "value": True},
            {"type": "condition", "field": "strength.value", "operator": ">=", "value": 80},
        ]
    },
}
