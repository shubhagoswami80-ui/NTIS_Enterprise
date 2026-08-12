from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

def load_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

def append_events(events: pd.DataFrame, path: Path):
    if events.empty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    header = not path.exists()
    events.to_csv(path, mode="a", index=False, header=header)

def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def save_state(state: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
