from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
DASHBOARD = ROOT / "dashboard.py"
BRIDGE_SRC = ROOT / "dashboard_evidence_bridge.py"
TARGET_BRIDGE = DASHBOARD.with_name("dashboard_evidence_bridge.py")

IMPORT_OLD = "from dashboard_evidence_bridge import build_live_evidence, resolve_alert_runtime\n"
IMPORT_NEW = "from dashboard_evidence_bridge import (build_live_evidence, resolve_alert_runtime, load_persisted_replay_observations)\n"

BLOCK_OLD = '''                _pit_frames = [\n                    frame for key, frame in cached_snapshots.items()\n                    if str(key).startswith("logical::")\n                    and isinstance(frame, pd.DataFrame)\n                    and not frame.empty\n                ]\n                _pit_history = (\n                    pd.concat(_pit_frames, ignore_index=True)\n                    if _pit_frames else pd.DataFrame()\n                )\n'''

BLOCK_NEW = '''                _pit_frames = [\n                    frame for key, frame in cached_snapshots.items()\n                    if str(key).startswith("logical::")\n                    and isinstance(frame, pd.DataFrame)\n                    and not frame.empty\n                ]\n                _current_pit_history = (\n                    pd.concat(_pit_frames, ignore_index=True)\n                    if _pit_frames else pd.DataFrame()\n                )\n                # LIVE PIT/EOD evidence must use already-persisted historical\n                # replay observations from prior trading sessions. This is a\n                # read-only cache read: it never runs replay or source rebuild.\n                _prior_pit_history, _pit_cache_meta = load_persisted_replay_observations(\n                    REPLAY_CACHE_ROOT, str(trading_date), max_sessions=30\n                )\n                _pit_history_frames = [\n                    frame for frame in (_prior_pit_history, _current_pit_history)\n                    if isinstance(frame, pd.DataFrame) and not frame.empty\n                ]\n                _pit_history = (\n                    pd.concat(_pit_history_frames, ignore_index=True)\n                    if _pit_history_frames else pd.DataFrame()\n                )\n'''


def main() -> int:
    if not DASHBOARD.is_file():
        print(f"dashboard.py not found: {DASHBOARD}")
        return 2
    if not BRIDGE_SRC.is_file():
        print(f"bridge source not found: {BRIDGE_SRC}")
        return 3

    text = DASHBOARD.read_text(encoding="utf-8")
    if IMPORT_NEW not in text:
        if IMPORT_OLD not in text:
            print("LIVE evidence import anchor not found; refusing patch.")
            return 4
        text = text.replace(IMPORT_OLD, IMPORT_NEW, 1)

    if BLOCK_NEW not in text:
        if BLOCK_OLD not in text:
            print("LIVE PIT history anchor not found; refusing patch.")
            return 5
        text = text.replace(BLOCK_OLD, BLOCK_NEW, 1)

    backup = DASHBOARD.with_name("dashboard.py.pre_live_evidence_source_alignment_v1.bak")
    shutil.copy2(DASHBOARD, backup)
    shutil.copy2(BRIDGE_SRC, TARGET_BRIDGE)
    DASHBOARD.write_text(text, encoding="utf-8")
    print(f"Patched dashboard: {DASHBOARD}")
    print(f"Installed bridge: {TARGET_BRIDGE}")
    print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
