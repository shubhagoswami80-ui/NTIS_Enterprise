from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

STORE_DIR_NAME = ".sector_intelligence"
STATUS_FILE = "status.json"
STATUS_PREFIX = "status_"
STATUS_SUFFIX = ".json"
RESULT_FILE = "latest.json"
LOCK_FILE = "worker.lock"
HISTORY_FILE = "history.json"
MANIFEST_FILE = "manifest.json"


def store_dir(package_dir: str | Path) -> Path:
    p = Path(package_dir).resolve() / STORE_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    """Create a JSON file once; never replace an existing status file."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(path, flags)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically persist durable result data."""
    import tempfile

    fd, tmp = tempfile.mkstemp(prefix=path.stem + "_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())

        last_error = None
        for _ in range(8):
            try:
                os.replace(tmp, path)
                return
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.05)
        if last_error is not None:
            raise last_error
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _status_snapshot_name() -> str:
    # Microseconds + PID makes collisions across rapid updates/processes
    # extremely unlikely; O_EXCL remains the final collision guard.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{STATUS_PREFIX}{stamp}_{os.getpid()}{STATUS_SUFFIX}"


def write_status(package_dir: str | Path, **payload: Any) -> None:
    """Publish an immutable status snapshot.

    The dashboard can safely read an older snapshot while the worker publishes
    the next one. No existing status file is replaced, so Windows sharing
    restrictions on a reader cannot cause WinError 5 during status updates.
    """
    directory = store_dir(package_dir)
    for _ in range(5):
        path = directory / _status_snapshot_name()
        try:
            _write_json_exclusive(path, payload)
            return
        except FileExistsError:
            time.sleep(0.001)
    raise RuntimeError("Unable to create a unique Sector Intelligence status snapshot")


def read_status(package_dir: str | Path) -> dict[str, Any]:
    """Read the newest completed immutable status snapshot."""
    directory = store_dir(package_dir)
    snapshots = sorted(directory.glob(f"{STATUS_PREFIX}*{STATUS_SUFFIX}"))
    for path in reversed(snapshots):
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            continue

    # Backward compatibility with pre-hotfix installations.
    legacy = directory / STATUS_FILE
    try:
        with legacy.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_result(package_dir: str | Path, payload: dict[str, Any]) -> None:
    _atomic_json(store_dir(package_dir) / RESULT_FILE, payload)


def read_result(package_dir: str | Path) -> dict[str, Any]:
    path = store_dir(package_dir) / RESULT_FILE
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_history(package_dir: str | Path, records: list[dict[str, Any]]) -> None:
    """Persist normalized sector observations for future historical processing."""
    _atomic_json(store_dir(package_dir) / HISTORY_FILE, {"records": records})


def read_history(package_dir: str | Path) -> list[dict[str, Any]]:
    path = store_dir(package_dir) / HISTORY_FILE
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        records = data.get("records", []) if isinstance(data, dict) else []
        return records if isinstance(records, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def write_manifest(package_dir: str | Path, manifest: dict[str, Any]) -> None:
    _atomic_json(store_dir(package_dir) / MANIFEST_FILE, manifest)


def read_manifest(package_dir: str | Path) -> dict[str, Any]:
    path = store_dir(package_dir) / MANIFEST_FILE
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
