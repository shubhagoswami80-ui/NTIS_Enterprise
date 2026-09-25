from __future__ import annotations

from typing import Any
import pandas as pd

from .engine import DifferentialConfig, PITDifferentialEngine


def build_differential_evidence(
    frame: pd.DataFrame,
    current_timestamp: Any | None = None,
    config: DifferentialConfig | None = None,
) -> dict[str, Any]:
    """Build display/audit evidence only; never alters SDL qualification."""
    result = PITDifferentialEngine(config).analyze(frame, current_timestamp)
    rows = result.rows
    unusual = rows[rows["unusual"]].copy() if not rows.empty else rows.copy()
    return {
        "rows": rows,
        "unusual_rows": unusual,
        "unusual_symbols": sorted(unusual["symbol"].dropna().unique().tolist())
        if not unusual.empty else [],
        "missing_metrics": result.missing_metrics,
        "current_timestamp": current_timestamp,
        "is_selection_gate": False,
    }
