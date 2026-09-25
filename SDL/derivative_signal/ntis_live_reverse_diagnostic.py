from __future__ import annotations

from datetime import date
from pathlib import Path
import inspect
import pandas as pd
import dashboard as d


def floor_s(v):
    t = pd.to_datetime(v, errors="coerce")
    if pd.isna(t):
        return None
    return pd.Timestamp(t).floor("s")


def frame_ts(frame):
    return floor_s(d._replay_frame_timestamp(frame))


def main():
    td = date.today().isoformat()
    root = Path(d.INTRADAY_SOURCE_ROOT)
    sources = d._sort_sources(d._discover_sources(td, root))
    groups = d._live_logical_snapshot_groups(sources)
    cache = d._get_replay_cache(td)
    snapshots = cache.get("snapshots", {}) if isinstance(cache, dict) else {}
    point = cache.get("point_in_time_cache", {}) if isinstance(cache, dict) else {}
    state = d.load_state(d.STATE_JSON)
    day = state.get(d.STATE_KEY, {}).get(td, {}) or {}
    saved = day.get("last_complete_state", {}) or {}
    checkpoint = floor_s(day.get("last_processed_observation_timestamp", saved.get("observation_timestamp", "")))

    source_times = [floor_s(d.parse_observation_timestamp(p)) for p in sources]
    source_times = [x for x in source_times if x is not None]
    snapshot_times = {frame_ts(v) for v in snapshots.values() if isinstance(v, pd.DataFrame)}
    snapshot_times.discard(None)
    point_times = {
        floor_s(v.get("source_timestamp"))
        for v in point.values()
        if isinstance(v, dict)
    }
    point_times.discard(None)

    print("=== NTIS SDL REVERSE LIVE DIAGNOSTIC ===")
    print(f"DATE                         : {td}")
    print(f"SOURCE ROOT                  : {root}")
    print(f"PHYSICAL SOURCE FILES        : {len(sources)}")
    print(f"LIVE LOGICAL GROUPS          : {len(groups)}")
    print(f"CHECKPOINT                   : {checkpoint}")
    print(f"LATEST SOURCE               : {max(source_times) if source_times else None}")
    print(f"REPLAY CACHE EXISTS          : {bool(cache)}")
    print(f"REPLAY SNAPSHOT ENTRIES      : {len(snapshots)}")
    print(f"POINT-IN-TIME ENTRIES        : {len(point)}")
    print(f"UNIQUE REPLAY TIMESTAMPS     : {len(snapshot_times)}")
    print(f"UNIQUE POINT-IN-TIME TIMES   : {len(point_times)}")
    print(f"CACHE COMPLETE FLAG          : {cache.get('complete') if isinstance(cache, dict) else None}")
    print(f"CACHE SOURCE COUNT           : {cache.get('source_count') if isinstance(cache, dict) else None}")

    print("\n--- LOGICAL GROUP / PHYSICAL FILE AUDIT ---")
    group_fail = []
    for i, group in enumerate(groups, 1):
        gt = floor_s(d._live_group_timestamp(group))
        try:
            assembled, _ = d._assemble_live_logical_snapshot(group, td)
            rows = len(assembled)
            err = ""
        except Exception as exc:
            rows = -1
            err = f"ASSEMBLY_ERROR={type(exc).__name__}: {exc}"
            group_fail.append((gt, err))
        print(f"{i:02d} {gt:%H:%M:%S} | physical_files={len(group):02d} | assembled_rows={rows:03d} | {err}")
        for p in group:
            print(f"     {p.name}")

    print("\n--- PER-GROUP CACHE / POINT-IN-TIME AUDIT ---")
    missing_snapshot = []
    missing_point = []
    for i, group in enumerate(groups, 1):
        gt = floor_s(d._live_group_timestamp(group))
        physical_times = {floor_s(d.parse_observation_timestamp(p)) for p in group}
        cached_group_times = {x for x in snapshot_times if x in physical_times}
        point_group_times = {x for x in point_times if x in physical_times}
        if cached_group_times != physical_times:
            missing_snapshot.append(gt)
        if point_group_times != physical_times:
            missing_point.append(gt)
        print(
            f"{i:02d} {gt:%H:%M:%S} | physical={len(group):02d} "
            f"| replay_entries={len(cached_group_times):02d} "
            f"| point_entries={len(point_group_times):02d} "
            f"| replay={'OK' if cached_group_times == physical_times else 'MISSING'} "
            f"| point={'OK' if point_group_times == physical_times else 'MISSING'}"
        )

    print("\n--- DURABLE STATE / SEQUENCE AUDIT ---")
    manifest = [floor_s(x) for x in day.get("processed_observation_timestamps", [])]
    manifest = [x for x in manifest if x is not None]
    print(f"PROCESSED MANIFEST COUNT      : {len(manifest)}")
    print(f"MANIFEST LAST                 : {max(manifest) if manifest else None}")
    print(f"CHECKPOINT == LATEST SOURCE  : {bool(source_times) and checkpoint == max(source_times)}")
    print(f"CHECKPOINT <= LATEST SOURCE  : {bool(source_times) and checkpoint is not None and checkpoint <= max(source_times)}")
    if manifest:
        print(f"MANIFEST MONOTONIC            : {manifest == sorted(manifest)}")
        print(f"MANIFEST UNIQUE               : {len(manifest) == len(set(manifest))}")

    print("\n--- LIVE AUTO-CYCLE CODE AUDIT ---")
    src = inspect.getsource(d._live_auto_panel)
    has_fragment = "@st.fragment" in src
    has_auto_process = "_auto_process_new_snapshots(" in src
    has_max_batch_1 = "max_batch=1" in src
    print(f"LIVE PANEL HAS SCHEDULED FRAGMENT: {has_fragment}")
    print(f"LIVE PANEL CALLS AUTO PROCESS      : {has_auto_process}")
    print(f"LIVE AUTO PROCESS MAX_BATCH=1      : {has_max_batch_1}")
    print("NOTE: if scheduled fragment is False, Auto-update can only process when the parent Streamlit render is triggered; the checkbox itself does not create a timer.")

    print("\n--- CURRENT SESSION STATE (if this process has no browser session, this is informational) ---")
    try:
        print(f"ds_auto_update                 : {d.st.session_state.get('ds_auto_update', '<not in this process>')}")
        print(f"ds_live_skip_processing_once  : {d.st.session_state.get('ds_live_skip_processing_once', False)}")
        print(f"backlog_active                : {d.st.session_state.get('ds_current_day_backlog_active', False)}")
    except Exception as exc:
        print(f"SESSION STATE READ ERROR       : {type(exc).__name__}: {exc}")

    print("\n--- VERDICT ---")
    if group_fail:
        print("REVIEW REQUIRED: logical snapshot assembly failed for one or more groups.")
    elif missing_snapshot or missing_point:
        print("REVIEW REQUIRED: one or more physical observations are absent from replay or point-in-time cache.")
    elif groups and checkpoint is not None:
        print("DATA CHAIN PASS: physical files are grouped and cache/point-in-time coverage is complete for the discovered groups.")
        if not has_fragment:
            print("AUTO-CYCLE FINDING: the current dashboard code has no periodic LIVE fragment. This is a separate issue from logical grouping and is a strong candidate for the observed Auto-update stall.")
        else:
            print("AUTO-CYCLE FINDING: scheduled LIVE fragment exists; inspect runtime invocation/timing next.")
    else:
        print("REVIEW REQUIRED: insufficient current-day state to establish the chain.")


if __name__ == "__main__":
    main()
