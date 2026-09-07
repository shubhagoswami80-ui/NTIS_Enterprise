from __future__ import annotations

import os
from pathlib import Path


def _path_env(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default))).expanduser().resolve()


# derivative_signal-local configuration.
# The established intraday source remains READ ONLY and is intentionally kept
# at the existing upstream SDL source location.
PROJECT_ROOT = Path(__file__).resolve().parent
INTRADAY_SOURCE_ROOT = _path_env(
    "SDL_INTRADAY_SOURCE_ROOT",
    Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot"),
)
