# NTIS SDL TRUE CURRENT DASHBOARD PROFILE V3
# Loaded automatically by Python through PYTHONPATH.
# This file does NOT import or modify the dashboard.
# It only observes function entry/return timings.

import atexit
import json
import os
import sys
import threading
import time
from pathlib import Path

_LOG = Path(os.environ.get(
    "NTIS_SDL_PROFILE_LOG",
    str(Path.cwd() / "function_timings.jsonl")
))

# Restrict tracing to the actual SDL source tree.
_SDL_ROOT = Path(os.environ.get(
    "NTIS_SDL_PROFILE_ROOT",
    str(Path.cwd())
)).resolve()

_TARGET_NAMES = {
    "discover_historical_snapshots",
    "process_snapshot",
    "replay_trading_date",
    "load_primary_snapshot",
    "_ensure_first_snapshot_base",
    "_apply_frozen_base",
    "_new_events",
    "load_events",
    "discover_daywise_files",
    "parse_observation_timestamp",
    "build_current_predictions",
}

# Per-thread call stacks. We only retain calls to selected functions.
_stacks = {}
_lock = threading.Lock()

def _path_is_sdl(filename):
    try:
        p = Path(filename).resolve()
        return p == _SDL_ROOT or _SDL_ROOT in p.parents
    except Exception:
        return False

def _write(row):
    try:
        with _lock:
            with _LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _profile(frame, event, arg):
    try:
        code = frame.f_code
        name = code.co_name

        if event == "call":
            if name not in _TARGET_NAMES:
                return

            filename = code.co_filename
            if not _path_is_sdl(filename):
                return

            key = threading.get_ident()
            _stacks.setdefault(key, []).append(
                (frame, time.perf_counter(), name, filename, code.co_firstlineno)
            )
            return

        if event == "return":
            key = threading.get_ident()
            stack = _stacks.get(key)
            if not stack:
                return

            # Usually the selected function is on top. Search from the top
            # defensively because unrelated calls are not retained.
            idx = None
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] is frame:
                    idx = i
                    break

            if idx is None:
                return

            _, started, fn, filename, lineno = stack.pop(idx)
            elapsed = time.perf_counter() - started

            _write({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "thread": key,
                "function": fn,
                "seconds": round(elapsed, 6),
                "file": str(Path(filename).resolve()),
                "line": lineno,
            })
    except Exception:
        pass

sys.setprofile(_profile)
threading.setprofile(_profile)

# Expose exact diagnostic locations to the process.
os.environ["NTIS_SDL_PROFILE_LOG"] = str(_LOG)
os.environ["NTIS_SDL_PROFILE_ROOT"] = str(_SDL_ROOT)

_write({
    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "event": "profile_started",
    "dashboard": str(_SDL_ROOT / "app_preview.py"),
})
