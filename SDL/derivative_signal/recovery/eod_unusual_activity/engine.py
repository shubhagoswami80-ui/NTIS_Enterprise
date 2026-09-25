from __future__ import annotations

from typing import Any, Iterable
import pandas as pd


DISPLAY_COLUMNS = (
    "symbol",
    "event",
    "current_timestamp",
    "current_value",
    "current_magnitude",
    "historical_median",
    "current_vs_median_ratio",
    "robust_z",
    "historical_sessions",
    "horizon_days",
    "unusual",
)


def _clean(frame: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=list(DISPLAY_COLUMNS))
    out = frame.copy()
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    if "current_timestamp" in out.columns:
        out["current_timestamp"] = pd.to_datetime(
            out["current_timestamp"], errors="coerce"
        )
    for col in ("current_vs_median_ratio", "robust_z", "current_magnitude"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "horizon_days" in out.columns:
        out["horizon_days"] = pd.to_numeric(
            out["horizon_days"], errors="coerce"
        ).astype("Int64")
    return out


def latest_point_in_time(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only the latest available differential observation.

    This is an EOD display boundary, not a trading/selection rule.
    """
    out = _clean(frame)
    if out.empty or "current_timestamp" not in out.columns:
        return out.iloc[0:0].copy()
    valid = out.dropna(subset=["current_timestamp"])
    if valid.empty:
        return valid.copy()
    latest = valid["current_timestamp"].max()
    return valid[valid["current_timestamp"].eq(latest)].copy()


def current_unusual_activity(
    frame: pd.DataFrame,
    *,
    latest_only: bool = True,
) -> pd.DataFrame:
    """Return current PIT differential rows that are explicitly unusual.

    The upstream PIT engine remains responsible for determining ``unusual``.
    This layer never creates a new unusual threshold and never selects stocks
    for SDL.
    """
    out = latest_point_in_time(frame) if latest_only else _clean(frame)
    if out.empty or "unusual" not in out.columns:
        return out.iloc[0:0].copy()
    unusual = out[out["unusual"].fillna(False).astype(bool)].copy()
    sort_cols = [
        c for c in
        ("symbol", "event", "horizon_days", "current_vs_median_ratio", "robust_z")
        if c in unusual.columns
    ]
    if sort_cols:
        ascending = [True, True, True, False, False][:len(sort_cols)]
        unusual = unusual.sort_values(sort_cols, ascending=ascending)
    return unusual.reset_index(drop=True)


def available_filter_values(
    frame: pd.DataFrame,
) -> dict[str, list[Any]]:
    """Build dynamic filter choices from the rows actually present."""
    out = _clean(frame)
    result: dict[str, list[Any]] = {}
    for col in ("symbol", "event", "horizon_days"):
        if col not in out.columns:
            result[col] = []
            continue
        values = [
            v for v in out[col].dropna().unique().tolist()
            if str(v).strip() not in {"", "NAN", "NAT"}
        ]
        result[col] = sorted(values, key=lambda x: str(x).upper())
    return result


def filter_current_unusual(
    frame: pd.DataFrame,
    *,
    symbols: Iterable[str] | None = None,
    events: Iterable[str] | None = None,
    horizons: Iterable[int] | None = None,
    min_ratio: float | None = None,
    min_robust_z: float | None = None,
) -> pd.DataFrame:
    """Apply display-only dynamic filters to current unusual activity."""
    out = current_unusual_activity(frame, latest_only=True)
    if out.empty:
        return out

    if symbols:
        wanted = {str(v).strip().upper() for v in symbols}
        out = out[out["symbol"].isin(wanted)]

    if events:
        wanted = {str(v).strip().upper() for v in events}
        out = out[out["event"].astype(str).str.upper().isin(wanted)]

    if horizons:
        wanted = {int(v) for v in horizons}
        out = out[out["horizon_days"].isin(wanted)]

    if min_ratio is not None and "current_vs_median_ratio" in out.columns:
        out = out[
            pd.to_numeric(out["current_vs_median_ratio"], errors="coerce")
            .ge(float(min_ratio))
        ]

    if min_robust_z is not None and "robust_z" in out.columns:
        out = out[
            pd.to_numeric(out["robust_z"], errors="coerce")
            .ge(float(min_robust_z))
        ]

    return out.reset_index(drop=True)


def current_unusual_symbols(frame: pd.DataFrame) -> list[str]:
    out = current_unusual_activity(frame)
    if out.empty or "symbol" not in out.columns:
        return []
    return sorted(out["symbol"].dropna().astype(str).str.upper().unique().tolist())


def eod_summary(frame: pd.DataFrame) -> dict[str, Any]:
    """Return compact audit metadata for the EOD unusual-activity panel."""
    out = current_unusual_activity(frame)
    timestamp = None
    if not out.empty and "current_timestamp" in out.columns:
        timestamp = out["current_timestamp"].max()
    return {
        "rows": len(out),
        "symbols": current_unusual_symbols(out),
        "events": sorted(out["event"].dropna().astype(str).unique().tolist())
        if not out.empty and "event" in out.columns else [],
        "timestamp": timestamp,
        "display_scope": "CURRENT_POINT_IN_TIME_UNUSUAL_ONLY",
        "selection_gate": False,
    }
