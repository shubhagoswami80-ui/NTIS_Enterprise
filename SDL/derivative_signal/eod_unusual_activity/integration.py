from __future__ import annotations

from typing import Any, Iterable
import pandas as pd

from .engine import (
    available_filter_values,
    current_unusual_activity,
    eod_summary,
    filter_current_unusual,
)


def build_eod_unusual_activity(
    differential_rows: pd.DataFrame,
    *,
    symbols: Iterable[str] | None = None,
    events: Iterable[str] | None = None,
    horizons: Iterable[int] | None = None,
    min_ratio: float | None = None,
    min_robust_z: float | None = None,
) -> dict[str, Any]:
    """Dashboard-ready EOD evidence; never changes SDL qualification."""
    current = current_unusual_activity(differential_rows)
    filtered = filter_current_unusual(
        current,
        symbols=symbols,
        events=events,
        horizons=horizons,
        min_ratio=min_ratio,
        min_robust_z=min_robust_z,
    )
    return {
        "rows": filtered,
        "unfiltered_current_unusual": current,
        "filter_values": available_filter_values(current),
        "summary": eod_summary(current),
        "is_selection_gate": False,
    }
