from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .data_adapter import canonicalize_row
from .signal_engine import build_signal


def replay_rows(rows: Iterable[dict]) -> list[dict]:
    previous_by_symbol: dict[str, dict] = {}
    results: list[dict] = []

    for raw in rows:
        current = canonicalize_row(raw)
        symbol = str(current.get("Symbol", "")).strip().upper()
        results.append(build_signal(current, previous_by_symbol.get(symbol)))
        previous_by_symbol[symbol] = current

    return results


def replay_workbook_sequence(paths: list[Path]) -> pd.DataFrame:
    """Replay selected workbooks in chronological order without changing upstream data."""
    all_results: list[dict] = []

    for path in sorted(paths, key=lambda p: p.stat().st_mtime):
        df = pd.read_excel(path)
        df.columns = [str(c).strip() for c in df.columns]
        rows = replay_rows(df.to_dict(orient="records"))
        for result in rows:
            result["source_file"] = path.name
        all_results.extend(rows)

    return pd.DataFrame(all_results)


def replay_single_workbook(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return pd.DataFrame(replay_rows(df.to_dict(orient="records")))
