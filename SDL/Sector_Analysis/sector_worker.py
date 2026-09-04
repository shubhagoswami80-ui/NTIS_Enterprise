from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_SDL = PACKAGE_DIR.parent
if str(PROJECT_SDL) not in sys.path:
    sys.path.insert(0, str(PROJECT_SDL))

from Sector_Analysis.sector_data_loader import (
    aggregate_sector_rows,
    find_sector_summary_candidates,
    load_sector_summary_snapshot,
)
from Sector_Analysis.sector_data_store import (
    LOCK_FILE,
    read_history,
    read_manifest,
    read_result,
    store_dir,
    write_history,
    write_manifest,
    write_result,
    write_status,
)
from Sector_Analysis.sector_rotation_engine import build_sector_intelligence


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _lock_path() -> Path:
    return store_dir(PACKAGE_DIR) / LOCK_FILE


def _is_running() -> bool:
    p = _lock_path()
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
        if os.name == "nt":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _write_lock() -> None:
    _lock_path().write_text(json.dumps({"pid": os.getpid(), "started_at": _now()}), encoding="utf-8")


def _remove_lock() -> None:
    try:
        _lock_path().unlink()
    except FileNotFoundError:
        pass


def _signature(path: Path) -> str:
    st = path.stat()
    return f"{st.st_size}:{st.st_mtime_ns}:{getattr(st, 'st_ctime_ns', 0)}"


def _safe_records(frame: pd.DataFrame) -> list[dict]:
    if frame.empty:
        return []
    # Convert NaN/NaT to JSON-safe None while preserving the actual observed values.
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _persist_history_frame(history: pd.DataFrame) -> None:
    write_history(PACKAGE_DIR, _safe_records(history))


def run(source_root: str | Path) -> None:
    if _is_running():
        return

    _write_lock()
    logs: list[str] = []
    try:
        root = Path(source_root).expanduser().resolve()
        manifest = read_manifest(PACKAGE_DIR)
        history_records = read_history(PACKAGE_DIR)

        # First run: build the durable historical layer. Later runs inspect only
        # file metadata first, then open only new/changed Sector Summary files.
        first_build = not bool(manifest) or not history_records
        candidates = find_sector_summary_candidates(root)
        total = len(candidates)

        write_status(
            PACKAGE_DIR,
            status="RUNNING",
            stage="DISCOVERY",
            progress=0,
            message="Checking Sector Summary source arrivals…",
            files_done=0,
            files_total=total,
            snapshots=0,
            cached_history=len(history_records),
            logs=logs[-20:],
            started_at=_now(),
        )

        pending: list[tuple[Path, str]] = []
        for path in candidates:
            try:
                sig = _signature(path)
            except OSError:
                continue
            key = str(path)
            if first_build or manifest.get(key, {}).get("signature") != sig:
                pending.append((path, sig))

        if not pending:
            logs.append(f"{_now()} · No new/changed Sector Summary files · using cached history")
            history = pd.DataFrame(history_records)
            if not history.empty and "observed_at" in history.columns:
                history["observed_at"] = pd.to_datetime(history["observed_at"], errors="coerce")
                history = history.sort_values(["observed_at", "sector"], kind="stable")

            write_status(
                PACKAGE_DIR,
                status="RUNNING",
                stage="INTELLIGENCE",
                progress=80,
                message="Rebuilding intelligence from cached historical observations…",
                files_done=total,
                files_total=total,
                snapshots=len(history_records),
                records=len(history),
                logs=logs[-20:],
                updated_at=_now(),
            )
            intelligence = build_sector_intelligence(history)
            latest = pd.to_datetime(history["observed_at"], errors="coerce").max() if not history.empty else pd.NaT
            payload = {
                "generated_at": _now(),
                "latest_observation": latest,
                "snapshot_count": len({r.get("_source_signature") for r in history_records if r.get("_source_signature")}),
                "record_count": len(history),
                "sessions": sorted({pd.Timestamp(v).strftime("%Y-%m-%d") for v in history["observed_at"].dropna()}) if not history.empty else [],
                "intelligence": intelligence,
            }
            write_result(PACKAGE_DIR, payload)
            write_status(
                PACKAGE_DIR,
                status="READY",
                stage="READY",
                progress=100,
                message="Sector intelligence ready.",
                files_done=total,
                files_total=total,
                snapshots=payload["snapshot_count"],
                records=len(history),
                logs=logs[-20:],
                updated_at=_now(),
                latest_observation=str(latest),
                mode="CACHED_HISTORY",
            )
            return

        # Only changed/new files are opened. Status publication is deliberately
        # throttled so hundreds of immutable status files are not created.
        total_pending = len(pending)
        records_to_add: list[dict] = []
        last_publish = 0.0
        for idx, (path, sig) in enumerate(pending, start=1):
            loaded = load_sector_summary_snapshot(path)
            added = 0
            for snap in loaded:
                frame = aggregate_sector_rows(snap)
                if frame.empty:
                    continue
                rows = frame.to_dict(orient="records")
                for row in rows:
                    row["observed_at"] = snap.observed_at.isoformat()
                    row["_source_signature"] = sig
                    row["_source_file"] = str(path)
                records_to_add.extend(rows)
                added += len(rows)

            manifest[str(path)] = {
                "signature": sig,
                "observed_at": max((s.observed_at.isoformat() for s in loaded), default=""),
                "processed_at": _now(),
                "records_added": added,
            }
            logs.append(f"{_now()} · Processed {path.name} · {added} sector rows")
            now = time.monotonic()
            if idx == total_pending or now - last_publish >= 0.75:
                write_status(
                    PACKAGE_DIR,
                    status="RUNNING",
                    stage="HISTORY",
                    progress=round(10 + 65 * idx / max(total_pending, 1), 1),
                    message=f"Building historical sector evidence {idx}/{total_pending} new/changed files…",
                    files_done=idx,
                    files_total=total_pending,
                    snapshots=len(manifest),
                    records=len(history_records) + len(records_to_add),
                    logs=logs[-20:],
                    updated_at=_now(),
                )
                last_publish = now

        history_records.extend(records_to_add)
        write_history(PACKAGE_DIR, history_records)
        write_manifest(PACKAGE_DIR, manifest)

        history = pd.DataFrame(history_records)
        if not history.empty:
            history["observed_at"] = pd.to_datetime(history["observed_at"], errors="coerce")
            history = history.dropna(subset=["observed_at", "sector"]).sort_values(["observed_at", "sector"], kind="stable")

        write_status(
            PACKAGE_DIR,
            status="RUNNING",
            stage="INTELLIGENCE",
            progress=85,
            message="Calculating material sector rotation from retained history…",
            snapshots=len(manifest),
            records=len(history),
            logs=logs[-20:],
            updated_at=_now(),
        )
        intelligence = build_sector_intelligence(history)

        latest = history["observed_at"].max() if not history.empty else pd.NaT
        payload = {
            "generated_at": _now(),
            "latest_observation": latest,
            "snapshot_count": len(manifest),
            "record_count": len(history),
            "sessions": sorted({v.strftime("%Y-%m-%d") for v in history["observed_at"].dropna()}),
            "intelligence": intelligence,
        }
        write_result(PACKAGE_DIR, payload)
        logs.append(
            f"{_now()} · Material rotation analysis complete · "
            f"{len(intelligence.get('focus', []))} focus · {len(intelligence.get('watch', []))} watch"
        )
        write_status(
            PACKAGE_DIR,
            status="READY",
            stage="READY",
            progress=100,
            message="Sector intelligence ready.",
            snapshots=len(manifest),
            records=len(history),
            logs=logs[-20:],
            updated_at=_now(),
            latest_observation=str(latest),
            mode="INCREMENTAL",
        )
    except Exception as exc:
        logs.append(f"{_now()} · ERROR · {type(exc).__name__}: {exc}")
        write_status(
            PACKAGE_DIR,
            status="ERROR",
            stage="ERROR",
            progress=100,
            message="Sector intelligence processor stopped with an error.",
            logs=logs[-20:],
            updated_at=_now(),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        _remove_lock()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    args = parser.parse_args()
    run(args.source_root)


if __name__ == "__main__":
    main()
