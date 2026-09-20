"""Streamlit UI for the isolated B3 Universal Alert Engine.

This module is intentionally self-contained. Import it from the Decision Centre only
through the integration boundary after read-only regression validation.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .alert_settings import PRESETS, rule_template
from .alert_rules import evaluate_rule, validate_rule
from .field_registry import FIELDS, get_field, field_keys

OPERATORS = [
    "=", "!=", ">", ">=", "<", "<=",
    "CROSSED_ABOVE", "CROSSED_BELOW", "ENTERED_RANGE", "EXITED_RANGE",
    "BECAME_TRUE", "BECAME_FALSE", "CHANGED_TO",
]
GROUPS = ["ALL", "ANY", "NOT"]
REARM_MODES = ["ON_CROSSING", "COOLDOWN", "ONCE_PER_SYMBOL_DAY", "MANUAL"]


def _field_items() -> list[tuple[str, str]]:
    """Return stable (key, label) pairs from the registry without requiring a UI import."""
    items = []
    for spec in FIELDS:
        items.append((spec.key, spec.label))
    return items


def _condition_default(field: str) -> dict[str, Any]:
    try:
        spec = get_field(field)
        kind = spec.kind
    except KeyError:
        kind = "number"
    value: Any = 0 if kind == "number" else False if kind == "boolean" else ""
    return {"type": "condition", "field": field, "operator": "=", "value": value}


def _condition_editor(st, node: dict[str, Any], key: str) -> dict[str, Any]:
    fields = _field_items()
    field_keys = [x[0] for x in fields]
    current_field = node.get("field", field_keys[0] if field_keys else "")
    if current_field not in field_keys and field_keys:
        current_field = field_keys[0]
    field = st.selectbox(
        "Field", field_keys,
        index=field_keys.index(current_field) if current_field in field_keys else 0,
        format_func=lambda x: next((label for k, label in fields if k == x), x),
        key=f"{key}_field",
    )
    operator = st.selectbox(
        "Operator", OPERATORS,
        index=OPERATORS.index(node.get("operator", "=")) if node.get("operator", "=") in OPERATORS else 0,
        key=f"{key}_operator",
    )
    try:
        spec = get_field(field)
        kind = spec.kind
    except KeyError:
        kind = "number"
    old = node.get("value", _condition_default(field)["value"])
    if kind == "boolean":
        value = st.checkbox("Value", value=bool(old), key=f"{key}_value_bool")
    elif kind == "text":
        value = st.text_input("Value", value=str(old), key=f"{key}_value_text")
    else:
        try:
            numeric = float(old)
            if numeric.is_integer():
                numeric = int(numeric)
        except (TypeError, ValueError):
            numeric = 0.0
        value = st.number_input("Value", value=numeric, key=f"{key}_value_num")
    return {"type": "condition", "field": field, "operator": operator, "value": value}


def _render_group(st, node: dict[str, Any], path: str, depth: int = 0) -> dict[str, Any]:
    operator = st.selectbox(
        "Group", GROUPS,
        index=GROUPS.index(node.get("operator", "ALL")) if node.get("operator", "ALL") in GROUPS else 0,
        key=f"{path}_group",
    )
    children = list(node.get("children", []))
    rendered: list[dict[str, Any]] = []
    remove_index: int | None = None
    for idx, child in enumerate(children):
        box = st.container(border=True)
        with box:
            st.caption(f"Condition/group {idx + 1}")
            if child.get("type") == "group":
                rendered_child = _render_group(st, child, f"{path}_{idx}", depth + 1)
            else:
                rendered_child = _condition_editor(st, child, f"{path}_{idx}")
            if st.button("Remove", key=f"{path}_{idx}_remove"):
                remove_index = idx
            else:
                rendered.append(rendered_child)
    cols = st.columns(2)
    with cols[0]:
        if st.button("+ Condition", key=f"{path}_add_condition"):
            rendered.append(_condition_default(_field_items()[0][0]))
    with cols[1]:
        if st.button("+ Group", key=f"{path}_add_group"):
            rendered.append({"type": "group", "operator": "ALL", "children": []})
    return {"type": "group", "operator": operator, "children": rendered}


def render_rule_builder(st, *, store=None, current_context: dict[str, Any] | None = None) -> None:
    """Render the complete B3 rule-builder panel.

    The caller supplies a Streamlit module/object so this file remains importable in
    unit tests without Streamlit installed.
    """
    st.subheader("Alert Rules")
    if "b3_alert_rule" not in st.session_state:
        st.session_state.b3_alert_rule = rule_template()
    rule = st.session_state.b3_alert_rule

    preset_names = ["Custom"] + list(PRESETS)
    preset = st.selectbox("Preset", preset_names, key="b3_alert_preset")
    if preset != "Custom" and st.button("Load preset", key="b3_load_preset"):
        rule["root"] = copy.deepcopy(PRESETS[preset])
        st.session_state.b3_alert_rule = rule
        st.rerun()

    top = st.columns(4)
    with top[0]:
        rule["name"] = st.text_input("Rule name", value=rule.get("name", "New Alert"), key="b3_rule_name")
    with top[1]:
        rule["enabled"] = st.checkbox("Enabled", value=bool(rule.get("enabled", True)), key="b3_rule_enabled")
    with top[2]:
        rule["priority"] = int(st.number_input("Priority", min_value=0, max_value=1000, value=int(rule.get("priority", 50)), key="b3_rule_priority"))
    with top[3]:
        rearm = rule.setdefault("rearm", {"mode": "ON_CROSSING", "cooldown_seconds": 0})
        rearm["mode"] = st.selectbox("Re-arm", REARM_MODES, index=REARM_MODES.index(rearm.get("mode", "ON_CROSSING")), key="b3_rearm_mode")
        if rearm["mode"] == "COOLDOWN":
            rearm["cooldown_seconds"] = int(st.number_input("Cooldown seconds", min_value=0, value=int(rearm.get("cooldown_seconds", 0)), key="b3_cooldown"))

    st.markdown("**Conditions**")
    rule["root"] = _render_group(st, rule.get("root", {"type": "group", "operator": "ALL", "children": []}), "b3_root")

    try:
        validate_rule(rule)
        st.success("Rule structure valid")
    except Exception as exc:
        st.error(f"Rule invalid: {exc}")

    actions = st.columns(3)
    with actions[0]:
        if st.button("Save rule", type="primary", key="b3_save_rule"):
            validate_rule(rule)
            if store is None:
                st.warning("Alert store is not connected in this read-only UI.")
            else:
                from datetime import datetime, timezone
                store.save_rule(rule, datetime.now(timezone.utc).isoformat())
                st.success("Rule saved")
    with actions[1]:
        if st.button("Test current snapshot", key="b3_test_rule"):
            if not current_context:
                st.info("No current snapshot supplied.")
            else:
                result = evaluate_rule(rule, current_context)
                (st.success if result.matched else st.info)("MATCHED" if result.matched else "NOT MATCHED")
                if result.reasons:
                    st.caption(" • ".join(result.reasons))
    with actions[2]:
        if st.button("Reset", key="b3_reset_rule"):
            st.session_state.b3_alert_rule = rule_template()
            st.rerun()


def render_alert_history(st, *, store, limit: int = 50) -> None:
    """Render compact, bounded alert history; no unbounded DB read."""
    st.subheader("Alert History")
    if store is None:
        st.info("Alert store is not connected.")
        return
    events = store.recent_events(limit=max(1, min(int(limit), 200)))
    if not events:
        st.caption("No alert events recorded yet.")
        return
    rows = []
    for event in events:
        rows.append({
            "TIME": event.get("observation_timestamp", ""),
            "STOCK": event.get("symbol", ""),
            "DIRECTION": event.get("direction", ""),
            "STRENGTH": event.get("strength", ""),
            "RULE": event.get("rule_name", event.get("rule_id", "")),
            "MATCH": " | ".join(event.get("matched_conditions", [])),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
