from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Iterable


TERMINAL_REVERSAL = "REVERSAL"
STATE_IDLE = "IDLE"
STATE_ACTIVE = "ACTIVE"
STATE_WATCH = "WATCH"
STATE_REENTRY_ALERT = "RE-ENTRY ALERT"


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        n = float(value)
        return n if n == n and abs(n) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip().upper()


def _direction(row: dict[str, Any]) -> str:
    value = _text(row.get("decision_direction", row.get("direction", "")))
    return value if value in {"BULLISH", "BEARISH"} else "NEUTRAL"


def _price(row: dict[str, Any]) -> float | None:
    for key in ("reference_price", "close", "Close", "price", "Price", "CMP", "cmp"):
        value = _num(row.get(key))
        if value is not None:
            return value
    return None


def _level(row: dict[str, Any], direction: str) -> float | None:
    keys = (
        ("camarilla_r3", "R3", "r3", "resistance", "Resistance")
        if direction == "BULLISH"
        else ("camarilla_s3", "S3", "s3", "support", "Support")
    )
    for key in keys:
        value = _num(row.get(key))
        if value is not None:
            return value
    return None


def _opposite_evidence(row: dict[str, Any], direction: str) -> bool:
    """Detect explicit opposite evidence only; never invent a second gate."""
    opposite = _text(row.get("opposite_evidence", row.get("retracement_opposite_evidence", "")))
    if opposite in {"TRUE", "YES", "1", "REVERSAL", "OPPOSITE"}:
        return True
    evidence_direction = _text(row.get("evidence_direction", ""))
    if evidence_direction in {"BULLISH", "BEARISH"} and evidence_direction != direction:
        return True
    decision_direction = _direction(row)
    return decision_direction in {"BULLISH", "BEARISH"} and decision_direction != direction


def _recovery(row: dict[str, Any], direction: str, anchor: float | None) -> bool:
    price = _price(row)
    if price is None or anchor is None:
        return False
    # Recovery means price has returned through the structural level in the
    # original direction after a retracement/watch event.
    return price > anchor if direction == "BULLISH" else price < anchor


def _touches_level(row: dict[str, Any], direction: str, anchor: float | None) -> bool:
    price = _price(row)
    if price is None or anchor is None:
        return False
    high = _num(row.get("high", row.get("High")))
    low = _num(row.get("low", row.get("Low")))
    if direction == "BULLISH":
        return (low is not None and low <= anchor) or price <= anchor
    return (high is not None and high >= anchor) or price >= anchor


def _structural_break(row: dict[str, Any], direction: str, level: float | None) -> bool:
    price = _price(row)
    if price is None or level is None:
        return False
    if direction == "BULLISH":
        return price > level
    return price < level


@dataclass
class RetracementState:
    symbol: str
    direction: str = "NEUTRAL"
    lifecycle: str = STATE_IDLE
    structural_break_anchor: float | None = None
    structural_break_timestamp: str = ""
    watch_timestamp: str = ""
    reentry_alert_timestamp: str = ""
    reversal_timestamp: str = ""
    alert_emitted: bool = False
    cycle_id: int = 0
    last_timestamp: str = ""
    ema20: float | None = None
    vwap: float | None = None
    rsi_5m: float | None = None
    rsi_15m: float | None = None
    rsi_30m: float | None = None
    rsi_60m: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetracementEngine:
    """Point-in-time retracement/re-entry state machine.

    Boundary contract:
      * Input is an already-qualified SDL row. This engine never ranks,
        filters, scores, or changes SDL qualification.
      * One observation in -> one deterministic state transition out.
      * Replay and LIVE use the same transition function.
      * RSI/EMA20/VWAP are evidence/display fields only.
    """

    def __init__(self) -> None:
        self._states: dict[str, RetracementState] = {}

    def get_state(self, symbol: str) -> RetracementState:
        key = _text(symbol)
        return self._states.setdefault(key, RetracementState(symbol=key))

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {symbol: state.to_dict() for symbol, state in self._states.items()}

    def restore(self, payload: dict[str, Any] | None) -> None:
        self._states.clear()
        if not isinstance(payload, dict):
            return
        for symbol, raw in payload.items():
            if not isinstance(raw, dict):
                continue
            try:
                self._states[_text(symbol)] = RetracementState(symbol=_text(symbol), **{
                    k: raw[k] for k in RetracementState.__dataclass_fields__ if k != "symbol" and k in raw
                })
            except (TypeError, ValueError):
                continue

    def process(self, row: dict[str, Any]) -> dict[str, Any]:
        symbol = _text(row.get("symbol", row.get("Symbol", "")))
        timestamp = str(row.get("observation_timestamp", row.get("source_timestamp", "")))
        direction = _direction(row)
        state = self.get_state(symbol)

        # Preserve the existing lifecycle once terminal until a fresh
        # structural break in the opposite/new direction starts a new cycle.
        if direction == "NEUTRAL":
            state.last_timestamp = timestamp
            return self._result(state, row, "NO_ACTION")

        if state.lifecycle == TERMINAL_REVERSAL:
            new_level = _level(row, direction)
            if direction != state.direction and _structural_break(row, direction, new_level):
                self._start_cycle(state, direction, new_level, timestamp)
            else:
                self._capture_evidence(state, row)
                state.last_timestamp = timestamp
                return self._result(state, row, "TERMINAL")

        if state.direction not in {"BULLISH", "BEARISH"}:
            level = _level(row, direction)
            if _structural_break(row, direction, level):
                self._start_cycle(state, direction, level, timestamp)
            else:
                self._capture_evidence(state, row)
                state.last_timestamp = timestamp
                return self._result(state, row, "WAIT_STRUCTURAL_BREAK")

        # Direction change is explicit opposite evidence. It invalidates the
        # current cycle and enters terminal reversal rather than emitting a
        # repeated re-entry alert.
        if direction != state.direction:
            self._capture_evidence(state, row)
            state.lifecycle = TERMINAL_REVERSAL
            state.reversal_timestamp = timestamp
            state.last_timestamp = timestamp
            return self._result(state, row, "REVERSAL")

        self._capture_evidence(state, row)
        anchor = state.structural_break_anchor

        if state.lifecycle in {STATE_ACTIVE, STATE_IDLE}:
            if _opposite_evidence(row, state.direction):
                state.lifecycle = TERMINAL_REVERSAL
                state.reversal_timestamp = timestamp
                state.last_timestamp = timestamp
                return self._result(state, row, "REVERSAL")
            if _touches_level(row, state.direction, anchor):
                state.lifecycle = STATE_WATCH
                state.watch_timestamp = timestamp
                state.last_timestamp = timestamp
                return self._result(state, row, "WATCH")
            state.lifecycle = STATE_ACTIVE
            state.last_timestamp = timestamp
            return self._result(state, row, "ACTIVE")

        if state.lifecycle == STATE_WATCH:
            if _opposite_evidence(row, state.direction):
                state.lifecycle = TERMINAL_REVERSAL
                state.reversal_timestamp = timestamp
                state.last_timestamp = timestamp
                return self._result(state, row, "REVERSAL")
            if _recovery(row, state.direction, anchor) and not state.alert_emitted:
                state.lifecycle = STATE_REENTRY_ALERT
                state.reentry_alert_timestamp = timestamp
                state.alert_emitted = True
                state.last_timestamp = timestamp
                return self._result(state, row, "RE-ENTRY ALERT")
            state.last_timestamp = timestamp
            return self._result(state, row, "WATCH")

        if state.lifecycle == STATE_REENTRY_ALERT:
            state.last_timestamp = timestamp
            return self._result(state, row, "NO_ACTION")

        state.last_timestamp = timestamp
        return self._result(state, row, "NO_ACTION")

    def _start_cycle(self, state: RetracementState, direction: str, anchor: float, timestamp: str) -> None:
        state.direction = direction
        state.lifecycle = STATE_ACTIVE
        state.structural_break_anchor = anchor
        state.structural_break_timestamp = timestamp
        state.watch_timestamp = ""
        state.reentry_alert_timestamp = ""
        state.reversal_timestamp = ""
        state.alert_emitted = False
        state.cycle_id += 1

    def _capture_evidence(self, state: RetracementState, row: dict[str, Any]) -> None:
        state.ema20 = _num(row.get("ema20", row.get("EMA20")))
        state.vwap = _num(row.get("vwap", row.get("VWAP")))
        for key, attr in (("rsi_5m", "rsi_5m"), ("rsi_15m", "rsi_15m"), ("rsi_30m", "rsi_30m"), ("rsi_60m", "rsi_60m")):
            setattr(state, attr, _num(row.get(key, row.get(key.upper()))))
        state.evidence = {
            "ema20": state.ema20,
            "vwap": state.vwap,
            "rsi_5m": state.rsi_5m,
            "rsi_15m": state.rsi_15m,
            "rsi_30m": state.rsi_30m,
            "rsi_60m": state.rsi_60m,
        }

    def _result(self, state: RetracementState, row: dict[str, Any], event: str) -> dict[str, Any]:
        return {
            "symbol": state.symbol,
            "observation_timestamp": str(row.get("observation_timestamp", row.get("source_timestamp", ""))),
            "direction": state.direction,
            "lifecycle": state.lifecycle,
            "interaction": event,
            "alert_type": event if event in {"RE-ENTRY ALERT", "REVERSAL"} else "",
            "alert_time": state.reentry_alert_timestamp or state.reversal_timestamp or "",
            "structural_break_anchor": state.structural_break_anchor,
            "structural_break_timestamp": state.structural_break_timestamp,
            "watch_timestamp": state.watch_timestamp,
            "reentry_alert_timestamp": state.reentry_alert_timestamp,
            "reversal_timestamp": state.reversal_timestamp,
            "cycle_id": state.cycle_id,
            "alert_emitted": state.alert_emitted,
            "ema20": state.ema20,
            "vwap": state.vwap,
            "rsi_5m": state.rsi_5m,
            "rsi_15m": state.rsi_15m,
            "rsi_30m": state.rsi_30m,
            "rsi_60m": state.rsi_60m,
        }


def process_observations(rows: Iterable[dict[str, Any]], initial_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    engine = RetracementEngine()
    if initial_state:
        engine.restore(initial_state)
    return [engine.process(dict(row)) for row in rows]
