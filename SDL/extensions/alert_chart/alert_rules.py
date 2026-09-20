from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

from .field_registry import get_field, resolve_field

COMPARATORS = {"=", "!=", ">", ">=", "<", "<="}
EVENT_OPERATORS = {"CROSSED_ABOVE", "CROSSED_BELOW", "ENTERED_RANGE", "EXITED_RANGE", "BECAME_TRUE", "BECAME_FALSE", "CHANGED_TO"}
GROUP_OPERATORS = {"ALL", "ANY", "NOT"}


@dataclass(frozen=True)
class RuleResult:
    matched: bool
    reasons: tuple[str, ...] = ()


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _eq(a: Any, b: Any) -> bool:
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return math.isclose(na, nb, rel_tol=1e-9, abs_tol=1e-9)
    return str(a).strip().casefold() == str(b).strip().casefold()


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator not in COMPARATORS:
        raise ValueError(f"Unsupported comparator: {operator}")
    if operator in {"=", "!="}:
        result = _eq(actual, expected)
        return result if operator == "=" else not result
    a, b = _num(actual), _num(expected)
    if a is None or b is None:
        return False
    return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[operator]


def _condition_label(c: dict[str, Any]) -> str:
    field = get_field(c["field"]).label
    op = c["operator"]
    if op in {"ENTERED_RANGE", "EXITED_RANGE"}:
        return f"{field} {op.replace('_', ' ').lower()} [{c.get('min')}, {c.get('max')}]"
    return f"{field} {op} {c.get('value')}"


def evaluate_condition(condition: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    field = condition["field"]
    get_field(field)
    op = str(condition["operator"]).upper()
    current = resolve_field(context, field)
    previous = resolve_field(context, field, previous=True)
    reasons = (_condition_label(condition),)

    if op in COMPARATORS:
        return RuleResult(_compare(current, op, condition.get("value")), reasons)

    if op == "CROSSED_ABOVE":
        p, c, threshold = _num(previous), _num(current), _num(condition.get("value"))
        return RuleResult(p is not None and c is not None and threshold is not None and p <= threshold < c, reasons)

    if op == "CROSSED_BELOW":
        p, c, threshold = _num(previous), _num(current), _num(condition.get("value"))
        return RuleResult(p is not None and c is not None and threshold is not None and p >= threshold > c, reasons)

    if op in {"ENTERED_RANGE", "EXITED_RANGE"}:
        p, c = _num(previous), _num(current)
        lo, hi = _num(condition.get("min")), _num(condition.get("max"))
        if None in (p, c, lo, hi):
            return RuleResult(False, reasons)
        prev_in, cur_in = lo <= p <= hi, lo <= c <= hi
        return RuleResult((not prev_in and cur_in) if op == "ENTERED_RANGE" else (prev_in and not cur_in), reasons)

    if op == "BECAME_TRUE":
        return RuleResult(previous is False and current is True, reasons)
    if op == "BECAME_FALSE":
        return RuleResult(previous is True and current is False, reasons)
    if op == "CHANGED_TO":
        return RuleResult(not _eq(previous, current) and _eq(current, condition.get("value")), reasons)
    raise ValueError(f"Unsupported alert operator: {op}")


def evaluate_node(node: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    node_type = str(node.get("type", "condition")).lower()
    if node_type == "condition":
        return evaluate_condition(node, context)

    op = str(node.get("operator", "ALL")).upper()
    children = node.get("children", [])
    if op not in GROUP_OPERATORS:
        raise ValueError(f"Unsupported group operator: {op}")
    results = [evaluate_node(child, context) for child in children]
    if op == "ALL":
        matched = bool(results) and all(r.matched for r in results)
    elif op == "ANY":
        matched = bool(results) and any(r.matched for r in results)
    else:
        matched = len(results) == 1 and not results[0].matched
    reasons = tuple(reason for r in results if r.matched for reason in r.reasons)
    return RuleResult(matched, reasons)


def validate_rule(rule: dict[str, Any]) -> None:
    if not rule.get("id") or not rule.get("name"):
        raise ValueError("Rule requires id and name")
    if not isinstance(rule.get("enabled", True), bool):
        raise ValueError("Rule.enabled must be boolean")
    if "root" not in rule:
        raise ValueError("Rule requires root condition/group")
    _validate_node(rule["root"])


def _validate_node(node: dict[str, Any]) -> None:
    node_type = str(node.get("type", "condition")).lower()
    if node_type == "condition":
        field = node.get("field")
        get_field(field)
        op = str(node.get("operator", "")).upper()
        if op not in COMPARATORS | EVENT_OPERATORS:
            raise ValueError(f"Unsupported operator: {op}")
        if op in {"ENTERED_RANGE", "EXITED_RANGE"}:
            if "min" not in node or "max" not in node:
                raise ValueError(f"{op} requires min and max")
        elif "value" not in node:
            raise ValueError(f"{op} requires value")
        return
    op = str(node.get("operator", "")).upper()
    if op not in GROUP_OPERATORS:
        raise ValueError(f"Unsupported group operator: {op}")
    children = node.get("children")
    if not isinstance(children, list) or not children:
        raise ValueError(f"{op} requires children")
    if op == "NOT" and len(children) != 1:
        raise ValueError("NOT requires exactly one child")
    for child in children:
        _validate_node(child)


def evaluate_rule(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    validate_rule(rule)
    if not rule.get("enabled", True):
        return RuleResult(False, ())
    return evaluate_node(rule["root"], context)
