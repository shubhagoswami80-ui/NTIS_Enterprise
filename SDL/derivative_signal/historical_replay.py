from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .data_adapter import canonicalize_row
from .signal_engine import build_signal, enrich_cross_sectional_evidence


def replay_rows(rows: Iterable[dict]) -> list[dict]:
    previous_by_symbol: dict[str, dict] = {}
    results: list[dict] = []

    for raw in rows:
        current = canonicalize_row(raw)
        symbol = str(current.get("Symbol", "")).strip().upper()
        results.append(
            build_signal(
                current,
                previous_by_symbol.get(symbol),
            )
        )
        previous_by_symbol[symbol] = current

    return enrich_cross_sectional_evidence(results)


def replay_workbook_sequence(paths: list[Path]) -> pd.DataFrame:
    """Replay selected workbooks chronologically without modifying source data."""
    all_results: list[dict] = []

    for sequence_index, path in enumerate(
        sorted(paths, key=lambda p: p.stat().st_mtime)
    ):
        df = pd.read_excel(path)
        df.columns = [str(c).strip() for c in df.columns]

        snapshot_results = replay_rows(
            df.to_dict(orient="records")
        )

        for result in snapshot_results:
            result["source_file"] = path.name
            result["replay_sequence"] = sequence_index

        all_results.extend(snapshot_results)

    return pd.DataFrame(all_results)


def replay_single_workbook(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return pd.DataFrame(
        replay_rows(df.to_dict(orient="records"))
    )
