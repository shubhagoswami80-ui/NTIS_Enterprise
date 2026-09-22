#!/usr/bin/env python
"""Monitored launcher for PCR Volume Pattern Discovery."""
from pathlib import Path
from datetime import datetime
import json, os, runpy, traceback

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "CONFIG.json").read_text(encoding="utf-8"))
OUT = Path(CONFIG["output_root"]) / "Current"
OUT.mkdir(parents=True, exist_ok=True)
STATUS = OUT / "pcr_volume_skew_live_status.json"
LOCK = OUT / "pcr_volume_pattern_discovery.lock"
CORE = BASE / "pcr_volume_pattern_discovery_core.py"

def write_status(state, **extra):
    payload = {
        "status": state,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        **extra,
    }
    STATUS.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, default=str), flush=True)

if not CORE.exists():
    write_status("ERROR", error=f"Core engine not found: {CORE}")
    raise SystemExit(1)

if LOCK.exists():
    write_status("BLOCKED", error=f"Lock exists: {LOCK}")
    raise SystemExit(2)

LOCK.write_text(
    json.dumps(
        {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds")},
        indent=2,
    ),
    encoding="utf-8",
)

try:
    write_status("STARTED", pid=os.getpid(), core_engine=CORE.name)
    write_status("RUNNING", note="Core discovery engine is processing source workbooks.")
    runpy.run_path(str(CORE), run_name="__main__")
    write_status("SUCCESS", note="Core discovery engine completed successfully.")
except Exception as exc:
    write_status("ERROR", error=str(exc), traceback=traceback.format_exc())
    raise
finally:
    LOCK.unlink(missing_ok=True)
