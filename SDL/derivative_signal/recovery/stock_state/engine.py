from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


@dataclass(frozen=True)
class StockState:
    symbol: str
    sdl_state: str | None
    retracement_state: str | None
    reentry_state: str | None
    rsi_15m: float | None
    rsi_30m: float | None
    rsi_1h: float | None
    rsi_2h: float | None
    mtf_alignment: str | None
    momentum_state: str | None
    state: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping and mapping[name] not in (None, ""):
            return mapping[name]
    return None


def _derive_state(sdl: str | None, retracement: str | None, reentry: str | None, momentum: str | None) -> str:
    # Presentation-only precedence. This does not alter any upstream gate.
    if retracement and retracement.upper() == "REVERSAL":
        return "REVERSAL"
    if reentry and reentry.upper() in {"RE-ENTRY ALERT", "REENTRY ALERT"}:
        return "RE-ENTRY ALERT"
    if retracement and retracement.upper() == "WATCH":
        return "RETRACEMENT WATCH"
    if momentum:
        return momentum
    return sdl or "UNKNOWN"


def compose_stock_state(
    record: Mapping[str, Any],
    *,
    retracement: Mapping[str, Any] | None = None,
    rsi: Mapping[str, Any] | None = None,
) -> StockState:
    """Compose descriptive state from already-produced evidence.

    The composer never calls SDL ranking, signal, replay, or qualification code.
    Missing evidence remains missing; it is not inferred or backfilled.
    """
    retracement = retracement or {}
    rsi = rsi or {}

    symbol = _text(_first(record, "symbol", "Symbol", "ticker", "Ticker")) or ""
    sdl_state = _text(_first(record, "sdl_state", "decision_state", "signal", "Signal"))
    retr_state = _text(_first(retracement, "lifecycle", "retracement_state", "state"))
    reentry = _text(_first(retracement, "alert_type", "reentry_state", "reentry"))

    r15 = _number(_first(rsi, "rsi_15m", "15m", "RSI_15M"))
    r30 = _number(_first(rsi, "rsi_30m", "30m", "RSI_30M"))
    r1h = _number(_first(rsi, "rsi_1h", "1h", "RSI_1H"))
    r2h = _number(_first(rsi, "rsi_2h", "2h", "RSI_2H"))
    alignment = _text(_first(rsi, "mtf_alignment", "alignment"))
    momentum = _text(_first(rsi, "momentum_state", "state"))

    return StockState(
        symbol=symbol,
        sdl_state=sdl_state,
        retracement_state=retr_state,
        reentry_state=reentry,
        rsi_15m=r15,
        rsi_30m=r30,
        rsi_1h=r1h,
        rsi_2h=r2h,
        mtf_alignment=alignment,
        momentum_state=momentum,
        state=_derive_state(sdl_state, retr_state, reentry, momentum),
    )
