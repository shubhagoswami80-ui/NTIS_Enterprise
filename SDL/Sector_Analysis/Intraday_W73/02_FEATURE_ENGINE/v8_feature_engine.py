"""
NTIS SDL Intraday W73 - V8 Feature Engine v1

Purpose
-------
Pure, Streamlit-free feature contract/engine for W73-A and W73-B.

Important:
- The preserved V8 maturity_feature_matrix.csv is authoritative for exact V8
  semantics. This module does NOT reconstruct V8 expressions from candidate text.
- Runtime accepts a point-in-time snapshot already normalized to the exact V8
  feature vocabulary.
- Missing values never become zero and never satisfy a strategy condition.
- W73-A and W73-B remain separate validated variants.

The engine also derives the two trajectory fields used by the frozen W73
candidate definitions from a point-in-time price sequence:
    px_all_negative_pre_maturity
    px_negative_count_pre_maturity

Trajectory derivation is strictly pre-maturity and point-in-time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import math


V8_FEATURE_COLUMNS = (
    "orb_minutes",
    "maturity",
    "orb_dir",
    "price_dir",
    "fut_dir",
    "option_dir",
    "fut_state",
    "volume_state",
    "ce_state",
    "pe_state",
    "pec_state",
    "fut_oi_state",
    "ce_pct_state",
    "pe_pct_state",
    "pec_pct_state",
    "fut_pct_state",
    "price_state",
    "orb_agree",
    "evidence_agreement",
    "persistent",
    "strength_bucket",
    "core_count_band",
    "magnitude_count_band",
    "orb_fut_agree",
    "orb_price_agree",
)

W73_A_CONDITION = {
    "orb_agree": "NO",
    "magnitude_count_band": 0,
    "px_all_negative_pre_maturity": True,
}

W73_B_CONDITION = {
    "orb_price_agree": "NO",
    "magnitude_count_band": 0,
    "px_all_negative_pre_maturity": True,
}


@dataclass(frozen=True)
class FeatureSnapshot:
    values: dict[str, Any]
    missing: tuple[str, ...]
    valid: bool
    reason: str = ""


@dataclass(frozen=True)
class TrajectoryFeatures:
    px_all_negative_pre_maturity: bool | None
    px_negative_count_pre_maturity: int | None
    observations_used: int


class V8FeatureEngine:
    """Build/validate a W73 point-in-time V8-compatible feature snapshot."""

    def __init__(self, exact_matrix_path: str | Path | None = None) -> None:
        self.exact_matrix_path = Path(exact_matrix_path) if exact_matrix_path else None

    @staticmethod
    def _missing(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

    @classmethod
    def validate_v8_snapshot(cls, snapshot: Mapping[str, Any]) -> FeatureSnapshot:
        missing = tuple(
            col for col in V8_FEATURE_COLUMNS
            if col not in snapshot or cls._missing(snapshot[col])
        )
        values = dict(snapshot)
        if missing:
            return FeatureSnapshot(
                values=values,
                missing=missing,
                valid=False,
                reason="Missing required exact-V8 feature fields",
            )
        return FeatureSnapshot(values=values, missing=(), valid=True)

    @staticmethod
    def _as_bool_direction(value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        token = str(value).strip().upper()
        if token in {"NEGATIVE", "DOWN", "BEARISH", "SELL", "-1"}:
            return False
        if token in {"POSITIVE", "UP", "BULLISH", "BUY", "+1", "1"}:
            return True
        return None

    def derive_trajectory(
        self,
        price_observations: Sequence[Mapping[str, Any]],
        *,
        maturity_timestamp: datetime,
        timestamp_key: str = "timestamp",
        price_change_key: str = "price_chg_pct",
    ) -> TrajectoryFeatures:
        """Derive pre-maturity negative-price trajectory without future leakage.

        A row is negative only when its price-change value is explicitly numeric
        and < 0. Missing/non-numeric values are excluded, never treated as zero.

        `px_all_negative_pre_maturity=True` requires at least one usable
        pre-maturity observation and every usable observation to be negative.
        """
        usable: list[float] = []

        for row in price_observations:
            raw_ts = row.get(timestamp_key)
            raw_change = row.get(price_change_key)
            if raw_ts is None or raw_change is None:
                continue

            try:
                ts = raw_ts if isinstance(raw_ts, datetime) else datetime.fromisoformat(str(raw_ts))
                value = float(raw_change)
            except (TypeError, ValueError):
                continue

            if ts >= maturity_timestamp:
                continue
            if math.isnan(value):
                continue
            usable.append(value)

        if not usable:
            return TrajectoryFeatures(None, None, 0)

        negatives = sum(1 for value in usable if value < 0)
        return TrajectoryFeatures(
            px_all_negative_pre_maturity=(negatives == len(usable)),
            px_negative_count_pre_maturity=negatives,
            observations_used=len(usable),
        )

    def build(
        self,
        snapshot: Mapping[str, Any],
        *,
        price_observations: Sequence[Mapping[str, Any]] | None = None,
        maturity_timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Return the W73 feature record.

        Exact V8 state fields are validated, not reconstructed. Trajectory fields
        are appended when a point-in-time price series and maturity timestamp are
        supplied.
        """
        checked = self.validate_v8_snapshot(snapshot)
        result = dict(checked.values)
        result["_v8_snapshot_valid"] = checked.valid
        result["_v8_missing_fields"] = list(checked.missing)
        result["_v8_validation_reason"] = checked.reason

        if price_observations is not None and maturity_timestamp is not None:
            trajectory = self.derive_trajectory(
                price_observations,
                maturity_timestamp=maturity_timestamp,
            )
            result["px_all_negative_pre_maturity"] = trajectory.px_all_negative_pre_maturity
            result["px_negative_count_pre_maturity"] = trajectory.px_negative_count_pre_maturity
            result["_trajectory_observations_used"] = trajectory.observations_used
        else:
            # Preserve an explicitly supplied point-in-time trajectory value.
            # Only fill from None when the caller did not provide the field.
            # Missing remains None; never coerce missing to False or zero.
            if "px_all_negative_pre_maturity" not in result:
                result["px_all_negative_pre_maturity"] = None
            if "px_negative_count_pre_maturity" not in result:
                result["px_negative_count_pre_maturity"] = None
            result["_trajectory_observations_used"] = 0

        return result

    @staticmethod
    def _exact_equal(actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        if isinstance(expected, bool):
            return actual is expected or str(actual).strip().lower() == str(expected).lower()
        if isinstance(expected, (int, float)):
            try:
                return float(actual) == float(expected)
            except (TypeError, ValueError):
                return False
        return str(actual).strip().upper() == str(expected).strip().upper()

    def match_variant(self, feature_record: Mapping[str, Any], variant: str) -> bool:
        conditions = {
            "W73-A": W73_A_CONDITION,
            "W73-B": W73_B_CONDITION,
        }.get(variant.upper())

        if conditions is None:
            raise ValueError(f"Unknown W73 variant: {variant!r}")

        if not bool(feature_record.get("_v8_snapshot_valid")):
            return False

        for field, expected in conditions.items():
            if field not in feature_record or self._missing(feature_record[field]):
                return False
            if not self._exact_equal(feature_record[field], expected):
                return False
        return True

    def match(self, feature_record: Mapping[str, Any]) -> dict[str, bool]:
        return {
            "W73-A": self.match_variant(feature_record, "W73-A"),
            "W73-B": self.match_variant(feature_record, "W73-B"),
        }
