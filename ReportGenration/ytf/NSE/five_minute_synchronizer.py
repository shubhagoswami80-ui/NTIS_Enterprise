#!/usr/bin/env python3
"""
Five-minute multi-source synchronizer.

Purpose:
- Collect/locate source snapshots belonging to a five-minute cycle.
- Allow small arrival-time differences.
- Never silently move late data into another cycle.
- Produce an immutable combined-cycle manifest.
- Keep raw source files untouched.

This component creates a synchronization manifest. It does not calculate
Premium Skew and does not invent missing NSE option-chain values.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def floor_cycle(dt: datetime, minutes: int = 5) -> datetime:
    return dt.replace(
        minute=(dt.minute // minutes) * minutes,
        second=0,
        microsecond=0,
    )


def inspect_file(path: Path, source_type: str, cycle: datetime, max_delay: int):
    stat = path.stat()
    arrival = datetime.fromtimestamp(stat.st_mtime)
    delta = (arrival - cycle).total_seconds()

    if delta < 0:
        status = "EARLY_OR_PREEXISTING"
    elif delta <= max_delay:
        status = "ON_TIME"
    else:
        status = "LATE"

    try:
        df = pd.read_excel(path, sheet_name=0)
        rows, columns = len(df), len(df.columns)
    except Exception as exc:
        rows, columns, status = None, None, "READ_ERROR"
        error = str(exc)
    else:
        error = ""

    return {
        "source_type": source_type,
        "source_file": path.name,
        "source_path": str(path),
        "arrival_timestamp": arrival.strftime("%Y-%m-%d %H:%M:%S"),
        "target_cycle": cycle.strftime("%Y-%m-%d %H:%M:%S"),
        "arrival_delta_seconds": round(delta, 1),
        "status": status,
        "rows": rows,
        "columns": columns,
        "error": error,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle-start", required=True,
                    help="Cycle start: YYYY-MM-DD HH:MM:SS")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--max-delay-seconds", type=int, default=120)
    ap.add_argument("--daywise")
    ap.add_argument("--resistance")
    ap.add_argument("--support-resistance")
    ap.add_argument("--nse-option-chain")
    args = ap.parse_args()

    cycle = floor_cycle(parse_dt(args.cycle_start))
    out_dir = Path(args.output_root) / cycle.strftime("%Y-%m-%d") / "synchronized"
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        ("daywise_price_oi", args.daywise),
        ("resistance_scan", args.resistance),
        ("support_resistance_scan", args.support_resistance),
        ("nse_option_chain", args.nse_option_chain),
    ]

    records = []
    for source_type, raw_path in candidates:
        if not raw_path:
            records.append({
                "source_type": source_type,
                "source_file": "",
                "source_path": "",
                "target_cycle": cycle.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "MISSING",
                "rows": None,
                "columns": None,
                "error": "No source path supplied",
            })
            continue

        path = Path(raw_path)
        if not path.exists():
            records.append({
                "source_type": source_type,
                "source_file": path.name,
                "source_path": str(path),
                "target_cycle": cycle.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "MISSING",
                "rows": None,
                "columns": None,
                "error": "File does not exist",
            })
            continue

        records.append(inspect_file(path, source_type, cycle, args.max_delay_seconds))

    statuses = {r["status"] for r in records}
    if "READ_ERROR" in statuses:
        overall = "REJECTED_READ_ERROR"
    elif "MISSING" in statuses:
        overall = "INCOMPLETE"
    elif "LATE" in statuses:
        overall = "INCOMPLETE_LATE_SOURCE"
    else:
        overall = "READY_FOR_ALIGNMENT"

    manifest = {
        "cycle_id": cycle.strftime("%Y%m%d_%H%M"),
        "target_cycle": cycle.strftime("%Y-%m-%d %H:%M:%S"),
        "cycle_length_minutes": 5,
        "max_delay_seconds": args.max_delay_seconds,
        "overall_status": overall,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": records,
        "policy": {
            "late_data_is_not_reassigned": True,
            "raw_files_are_not_overwritten": True,
            "combined_analysis_requires_all_required_sources": True,
        },
    }

    json_path = out_dir / f"cycle_{manifest['cycle_id']}_manifest.json"
    csv_path = out_dir / f"cycle_{manifest['cycle_id']}_manifest.csv"
    json_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pd.DataFrame(records).to_csv(csv_path, index=False)

    print(f"Cycle: {manifest['cycle_id']}")
    print(f"Overall status: {overall}")
    print(f"JSON manifest: {json_path}")
    print(f"CSV manifest: {csv_path}")


if __name__ == "__main__":
    main()
