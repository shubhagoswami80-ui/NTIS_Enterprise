from __future__ import annotations

from typing import Any

# Source fields are retained verbatim. This layer does not invent V8 semantics.
# V8 feature construction remains exclusively in 02_FEATURE_ENGINE.
REQUIRED_SOURCE_FIELDS = (
    "Symbol",
    "ATM Straddle Price",
    "ATM Straddle %",
    "Open",
    "High",
    "Low",
    "Close",
    "VWAP",
    "Price Chg",
    "Price Chg %",
    "IV",
    "IV Chg",
    "IV Chg %",
    "OI Chg",
    "OI Chg %",
    "Volume",
    "Volume Chg (%)",
    "PCR Chg",
    "PCR Chg %",
    "Buildup",
    "Tot CE OI",
    "Tot PE OI",
    "Tot PE-CE OI",
    "Tot CE OI Chg",
    "Tot CE OI Chg %",
    "Tot PE OI Chg",
    "Tot PE OI Chg %",
    "IVR",
    "IVP",
)


def canonicalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a W73 source observation without coercing missing values."""
    return {key: raw.get(key) for key in REQUIRED_SOURCE_FIELDS} | {
        "_source_extra_fields": {
            key: value for key, value in raw.items() if key not in REQUIRED_SOURCE_FIELDS
        }
    }
