from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from source_loader import parse_observation_timestamp


def observation_timestamp(path: Path) -> pd.Timestamp:
    """Match the existing SDL timestamp contract: filename, then file mtime."""
    try:
        return observation_timestamp(path)
    except Exception:
        return pd.Timestamp.fromtimestamp(path.stat().st_mtime)


# Files separated by <= this gap belong to the same observation bundle.
# This treats 09:20, 09:21 and 09:22 as one observation sequence when they
# arrive continuously, while preserving a new bundle after a real gap.
BUNDLE_GAP_SECONDS = 60


@dataclass(frozen=True)
class SnapshotBundle:
    trading_date: str
    timestamp: pd.Timestamp
    paths: tuple[Path, ...]

    @property
    def canonical_path(self) -> Path:
        # Existing SDL Daywise workbooks are complete primary snapshots.
        # Use the latest file in a bundle as the canonical snapshot so the
        # established pipeline remains the single decision engine.
        return self.paths[-1]

    @property
    def label(self) -> str:
        if len(self.paths) == 1:
            return self.timestamp.strftime("%H:%M:%S")
        first = parse_observation_timestamp(self.paths[0])
        last = parse_observation_timestamp(self.paths[-1])
        return f"{first.strftime('%H:%M:%S')}–{last.strftime('%H:%M:%S')} ({len(self.paths)} files)"


def _timestamp(path: Path) -> pd.Timestamp:
    return observation_timestamp(path)


def bundle_paths(paths: list[Path] | tuple[Path, ...], gap_seconds: int = BUNDLE_GAP_SECONDS) -> list[SnapshotBundle]:
    ordered = sorted((Path(p) for p in paths), key=lambda p: (_timestamp(p), str(p).lower()))
    if not ordered:
        return []

    groups: list[list[Path]] = [[ordered[0]]]
    for path in ordered[1:]:
        prev = _timestamp(groups[-1][-1])
        current = _timestamp(path)
        gap = (current - prev).total_seconds()
        if gap <= gap_seconds:
            groups[-1].append(path)
        else:
            groups.append([path])

    bundles: list[SnapshotBundle] = []
    for group in groups:
        ts = _timestamp(group[-1])
        bundles.append(
            SnapshotBundle(
                trading_date=ts.date().isoformat(),
                timestamp=ts,
                paths=tuple(group),
            )
        )
    return bundles


def bundles_for_date(discover_fn, trading_date: str) -> list[SnapshotBundle]:
    paths = [Path(p) for p in discover_fn(trading_date)]
    return bundle_paths(paths)


def next_bundle(bundles: list[SnapshotBundle], current_timestamp: pd.Timestamp | None) -> SnapshotBundle | None:
    if not bundles:
        return None
    if current_timestamp is None or pd.isna(current_timestamp):
        return bundles[0]
    for bundle in bundles:
        if bundle.timestamp > current_timestamp:
            return bundle
    return None


def bundle_for_timestamp(bundles: list[SnapshotBundle], timestamp: pd.Timestamp) -> SnapshotBundle | None:
    if timestamp is None or pd.isna(timestamp):
        return None
    for bundle in bundles:
        first = observation_timestamp(bundle.paths[0])
        last = observation_timestamp(bundle.paths[-1])
        if first <= timestamp <= last:
            return bundle
    return None
