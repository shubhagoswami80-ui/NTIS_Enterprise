from __future__ import annotations

import gzip
import pickle

import pandas as pd

from dashboard_evidence_bridge import load_persisted_replay_observations


def _write_cache(root, day, frame):
    root.mkdir(parents=True, exist_ok=True)
    value = {
        "version": 4,
        "trading_date": day,
        "snapshots": {f"logical::{day}T10:00:00": frame},
        "complete": True,
    }
    with gzip.open(root / f"{day}.pkl.gz", "wb") as handle:
        pickle.dump(value, handle)


def test_loader_reads_only_prior_logical_cache_frames(tmp_path):
    root = tmp_path / "replay_cache"
    _write_cache(root, "2026-09-20", pd.DataFrame([{
        "symbol": "TEST", "observation_timestamp": "2026-09-20 10:00:00", "Volume": 10,
    }]))
    _write_cache(root, "2026-09-21", pd.DataFrame([{
        "symbol": "TEST", "observation_timestamp": "2026-09-21 10:00:00", "Volume": 12,
    }]))
    _write_cache(root, "2026-09-22", pd.DataFrame([{
        "symbol": "TEST", "observation_timestamp": "2026-09-22 10:00:00", "Volume": 99,
    }]))

    frame, meta = load_persisted_replay_observations(root, "2026-09-22", max_sessions=30)
    assert set(frame["trading_date"].astype(str)) == {"2026-09-20", "2026-09-21"}
    assert frame["Volume"].tolist() == [10, 12]
    assert meta["sessions"] == 2


def test_loader_is_read_only_and_does_not_create_cache(tmp_path):
    root = tmp_path / "missing"
    frame, meta = load_persisted_replay_observations(root, "2026-09-22")
    assert frame.empty
    assert meta["missing_root"] is True
    assert not root.exists()
