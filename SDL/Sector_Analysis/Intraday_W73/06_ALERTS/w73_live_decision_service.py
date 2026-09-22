from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any, Sequence
import sys

ROOT = Path(__file__).resolve().parents[1]
FEATURE_DIR = ROOT / "02_FEATURE_ENGINE"
if str(FEATURE_DIR) not in sys.path:
    sys.path.insert(0, str(FEATURE_DIR))

from w73_exact_v8_live_engine import (  # noqa: E402
    MATURITY_CUTS,
    V8_COLUMNS,
    build_exact_v8,
)


@dataclass(frozen=True)
class LiveDecision:
    symbol: str
    trading_date: str
    maturity: str
    status: str
    variant: str | None
    action: str
    observation_timestamp: str
    source_timestamp: str
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    trajectory: dict[str, Any]
    feature_vector: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _asof(rows: Sequence[dict[str, Any]]) -> datetime | None:
    timestamps = [_parse_ts(r.get("_observation_timestamp", r.get("timestamp"))) for r in rows]
    timestamps = [x for x in timestamps if x is not None]
    return max(timestamps) if timestamps else None


def matured_cuts(asof: datetime | None) -> list[str]:
    if asof is None:
        return []
    return [
        label for label, cutoff in MATURITY_CUTS.items()
        if asof.time() >= cutoff
    ]


def _cutoff(trading_date: str, maturity: str) -> datetime:
    t = MATURITY_CUTS[maturity]
    return datetime.fromisoformat(trading_date).replace(
        hour=t.hour, minute=t.minute, second=0, microsecond=0
    )


def evaluate_symbol(
    rows: Sequence[dict[str, Any]],
    *,
    symbol: str,
    trading_date: str,
    maturity: str,
    orb_minutes: int = 15,
) -> LiveDecision:
    result = build_exact_v8(
        rows,
        symbol=symbol,
        trading_date=trading_date,
        maturity=maturity,
        orb_minutes=orb_minutes,
    )
    variant = None
    if result.variants.get("W73-A"):
        variant = "W73-A"
    elif result.variants.get("W73-B"):
        variant = "W73-B"

    if result.status != "READY":
        action = "NOT_READY"
    elif variant:
        action = "QUALIFIED"
    else:
        action = "WAIT"

    source_ts = ""
    if result.observation_timestamp:
        source_ts = result.observation_timestamp

    return LiveDecision(
        symbol=symbol.upper(),
        trading_date=trading_date,
        maturity=maturity,
        status=result.status,
        variant=variant,
        action=action,
        observation_timestamp=result.observation_timestamp,
        source_timestamp=source_ts,
        missing_fields=result.missing_fields,
        warnings=result.warnings,
        trajectory=result.trajectory,
        feature_vector=result.feature_vector,
    )


def evaluate_latest_maturity(
    rows: Sequence[dict[str, Any]],
    *,
    trading_date: str,
    symbols: Sequence[str] | None = None,
    orb_minutes: int = 15,
) -> tuple[datetime | None, str | None, list[LiveDecision]]:
    """Evaluate the latest maturity checkpoint that has actually elapsed.

    Only observations in the supplied PIT cache are passed to the engine.
    No future source file is admitted and no target/outcome field is used.
    """
    asof = _asof(rows)
    cuts = matured_cuts(asof)
    if not cuts:
        return asof, None, []

    maturity = cuts[-1]
    wanted = {str(s).strip().upper() for s in symbols} if symbols else None
    available = sorted({str(r.get("Symbol", "")).strip().upper() for r in rows if r.get("Symbol")})
    if wanted is not None:
        available = [s for s in available if s in wanted]

    decisions: list[LiveDecision] = []
    for symbol in available:
        symbol_rows = [
            r for r in rows
            if str(r.get("Symbol", "")).strip().upper() == symbol
            and (_parse_ts(r.get("_observation_timestamp", r.get("timestamp"))) or datetime.min)
            <= _cutoff(trading_date, maturity)
        ]
        if not symbol_rows:
            continue
        decisions.append(
            evaluate_symbol(
                symbol_rows,
                symbol=symbol,
                trading_date=trading_date,
                maturity=maturity,
                orb_minutes=orb_minutes,
            )
        )
    return asof, maturity, decisions


def decision_summary(decisions: Sequence[LiveDecision]) -> dict[str, int]:
    summary = {"QUALIFIED": 0, "WAIT": 0, "NOT_READY": 0}
    for d in decisions:
        summary[d.action] = summary.get(d.action, 0) + 1
    return summary
