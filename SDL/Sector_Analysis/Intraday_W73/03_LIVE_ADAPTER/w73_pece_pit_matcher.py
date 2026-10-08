"""
NTIS W73 - PE/CE point-in-time matcher.

Causal matching contract:
1. Authoritative Daywise observation timestamp is the decision/data boundary.
2. PECE Snapshot must be <= the causal boundary.
3. Among causally eligible PECE observations for the same trading date and
   symbol, choose the observation_time closest to the authoritative time.
4. A maximum observation-time gap is enforced.
5. File creation time is retained as lineage/diagnostic only; it never defines
   market time and never makes a later snapshot eligible.
6. Missing/unsafe PECE remains missing. No carry-forward, fabrication, or
   PE%-CE% reconstruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

try:
    from .w73_pece_source_adapter import PECERecord
except ImportError:
    from w73_pece_source_adapter import PECERecord


@dataclass(frozen=True)
class PECEPITMatch:
    match_status: str
    value: float | None
    direct_pct_state: str | None
    pece_oi_chg: float | None
    authoritative_timestamp: datetime
    authoritative_file_created_time: datetime | None
    pece_observation_time: datetime | None
    pece_snapshot_time: datetime | None
    pece_file_created_time: datetime | None
    match_delta_seconds: float | None
    snapshot_age_seconds: float | None
    source_file: str | None
    reason: str


def match_pece(
    *,
    trading_date: str,
    symbol: str,
    authoritative_timestamp: datetime,
    authoritative_file_created_time: datetime | None,
    records: Iterable[PECERecord],
    max_gap_seconds: int = 180,
) -> PECEPITMatch:
    candidates = []
    for record in records:
        if record.trading_date != trading_date:
            continue
        if record.symbol != symbol.upper():
            continue
        if record.pece_oi_chg_pct is None:
            continue
        if record.snapshot_time is None:
            # No explicit causal acquisition time: unsafe.
            continue
        if record.snapshot_time > authoritative_timestamp:
            continue
        if record.observation_time is None:
            continue
        delta = abs((record.observation_time - authoritative_timestamp).total_seconds())
        if delta > max_gap_seconds:
            continue
        candidates.append((delta, record))

    if not candidates:
        return PECEPITMatch(
            match_status="MISSING",
            value=None,
            direct_pct_state=None,
            pece_oi_chg=None,
            authoritative_timestamp=authoritative_timestamp,
            authoritative_file_created_time=authoritative_file_created_time,
            pece_observation_time=None,
            pece_snapshot_time=None,
            pece_file_created_time=None,
            match_delta_seconds=None,
            snapshot_age_seconds=None,
            source_file=None,
            reason="NO_CAUSALLY_ELIGIBLE_PECE_RECORD",
        )

    # Stable deterministic tie-break: closest observation time, then latest
    # causally available snapshot, then latest file creation time.
    candidates.sort(
        key=lambda x: (
            x[0],
            -(x[1].snapshot_time.timestamp()),
            -(x[1].file_created_time.timestamp() if x[1].file_created_time else float("-inf")),
        )
    )
    delta, chosen = candidates[0]
    snapshot_age = (
        authoritative_timestamp - chosen.snapshot_time
    ).total_seconds()

    return PECEPITMatch(
        match_status="MATCHED",
        value=chosen.pece_oi_chg_pct,
        direct_pct_state=chosen.direct_pct_state,
        pece_oi_chg=chosen.pece_oi_chg,
        authoritative_timestamp=authoritative_timestamp,
        authoritative_file_created_time=authoritative_file_created_time,
        pece_observation_time=chosen.observation_time,
        pece_snapshot_time=chosen.snapshot_time,
        pece_file_created_time=chosen.file_created_time,
        match_delta_seconds=delta,
        snapshot_age_seconds=snapshot_age,
        source_file=chosen.source_file,
        reason="CAUSAL_NEAREST_OBSERVATION",
    )
