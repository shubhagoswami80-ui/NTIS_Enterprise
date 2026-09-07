from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_state(path: str | Path) -> dict[str, Any]:
    """Load JSON state; return an empty state when the file is absent/invalid."""
    target = Path(path)
    try:
        with target.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def save_state(state: dict[str, Any], path: str | Path) -> None:
    """Atomically persist JSON state without changing the existing state schema."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, default=str)
        handle.flush()
    temp.replace(target)
