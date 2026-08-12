from __future__ import annotations

import os
from pathlib import Path


def _path_env(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default))).expanduser().resolve()


PROJECT_ROOT = Path(
    os.getenv("SDL_PROJECT_ROOT", str(Path(__file__).resolve().parent))
).expanduser().resolve()

# External source roots. These are READ ONLY and are never copied or modified.
EOD_SOURCE_ROOT = _path_env(
    "SDL_EOD_SOURCE_ROOT",
    Path(r"E:\NSE_Daily_Analysis\2026"),
)

INTRADAY_SOURCE_ROOT = _path_env(
    "SDL_INTRADAY_SOURCE_ROOT",
    Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot"),
)

# Optional direct input location for a manually supplied snapshot.
INPUT_DIR = _path_env(
    "SDL_INPUT_DIR",
    PROJECT_ROOT / "data" / "input",
)

# SDL-owned outputs.
OUTPUT_ROOT = _path_env(
    "SDL_OUTPUT_ROOT",
    PROJECT_ROOT / "data" / "output",
)

TRADABLE_EVENTS_DIR = _path_env(
    "SDL_TRADABLE_EVENTS_DIR",
    OUTPUT_ROOT / "tradable_events",
)

REQUIRED_EVIDENCE_DIR = _path_env(
    "SDL_REQUIRED_EVIDENCE_DIR",
    OUTPUT_ROOT / "required_evidence",
)

REPLAY_OUTCOMES_DIR = _path_env(
    "SDL_REPLAY_OUTCOMES_DIR",
    OUTPUT_ROOT / "replay_outcomes",
)

STATE_DIR = _path_env(
    "SDL_STATE_DIR",
    OUTPUT_ROOT / "state",
)

LOG_DIR = _path_env(
    "SDL_LOG_DIR",
    OUTPUT_ROOT / "logs",
)

EVENT_CSV = _path_env(
    "SDL_EVENT_CSV",
    TRADABLE_EVENTS_DIR / "breakout_events.csv",
)

STATE_JSON = _path_env(
    "SDL_STATE_JSON",
    STATE_DIR / "processing_state.json",
)

BREAKOUT_MULTIPLIER = float(
    os.getenv("SDL_BREAKOUT_MULTIPLIER", "1.0")
)

CURRENT_PRICE_FIELD = os.getenv(
    "SDL_CURRENT_PRICE_FIELD",
    "Close",
)

STRADDLE_FORMULA = os.getenv(
    "SDL_STRADDLE_FORMULA",
    "open_x_atm_straddle_pct",
)

STRATEGY_VERSION = os.getenv(
    "SDL_STRATEGY_VERSION",
    "SDL-P1-Standard-Straddle-v1.0",
)

DASHBOARD_PORT = int(
    os.getenv("SDL_DASHBOARD_PORT", "8504")
)

SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".csv"}

PRIMARY_COLUMNS = [
    "Symbol", "ATM Straddle %", "Open", "High", "Low", "Close",
    "Price Chg", "Price Chg %", "IV Chg", "IV Chg %",
    "OI Chg", "OI Chg %", "PCR Chg", "PCR Chg %",
    "Tot CE OI Chg", "Tot CE OI Chg %",
    "Tot PE OI Chg", "Tot PE OI Chg %",
    "Tot PE-CE OI Chg",
]


def ensure_runtime_directories() -> None:
    for path in (
        INPUT_DIR,
        TRADABLE_EVENTS_DIR,
        REQUIRED_EVIDENCE_DIR,
        REPLAY_OUTCOMES_DIR,
        STATE_DIR,
        LOG_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
