from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

def load_rows(cache_file: str|Path):
    p=Path(cache_file)
    if not p.exists(): return []
    rows=[]
    with p.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows

def latest_as_of(rows, cutoff: datetime|None=None):
    grouped={}
    for r in rows:
        ts=datetime.fromisoformat(r["_observation_timestamp"])
        if cutoff and ts>cutoff: continue
        sym=str(r.get("Symbol","")).strip().upper()
        if not sym: continue
        if sym not in grouped or ts>datetime.fromisoformat(grouped[sym]["_observation_timestamp"]):
            grouped[sym]=r
    return list(grouped.values())

def exact_timestamps(rows):
    return sorted({r["_observation_timestamp"] for r in rows})
