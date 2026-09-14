#!/usr/bin/env python3
"""
Hybrid five-minute cycle coordinator.

This is a conservative orchestration layer for the four feeds:
  - three supplementary workbook feeds
  - one NSE option-chain feed

It waits until the configured settling deadline, checks that all inputs exist,
and writes a cycle decision. It does not move late data into another cycle,
overwrite raw files, or calculate Premium Skew.

The coordinator is intended to be called by Task Scheduler or a controlled
collector process once per five-minute cycle.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path


def parse_dt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=None)


def cycle_floor(dt: datetime) -> datetime:
    return dt.replace(
        minute=(dt.minute // 5) * 5,
        second=0,
        microsecond=0,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle-start", required=True,
                    help="Cycle start, e.g. 2026-09-15 10:00:00")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--settling-seconds", type=int, default=60)
    ap.add_argument("--max-source-delay-seconds", type=int, default=120)
    ap.add_argument("--wait", action="store_true",
                    help="Wait until cycle end plus settling period")
    ap.add_argument("--daywise", required=True)
    ap.add_argument("--resistance", required=True)
    ap.add_argument("--support-resistance", required=True)
    ap.add_argument("--nse-option-chain", required=True)
    args = ap.parse_args()

    cycle = cycle_floor(parse_dt(args.cycle_start))
    cycle_end = cycle + timedelta(minutes=5)
    deadline = cycle_end + timedelta(seconds=args.settling_seconds)

    if args.wait:
        remaining = (deadline - datetime.now()).total_seconds()
        if remaining > 0:
            print(f"Waiting {int(remaining)} seconds for cycle settlement...")
            time.sleep(remaining)

    sources = {
        "daywise": Path(args.daywise),
        "resistance": Path(args.resistance),
        "support_resistance": Path(args.support_resistance),
        "nse_option_chain": Path(args.nse_option_chain),
    }

    source_status = []
    for name, path in sources.items():
        exists = path.exists()
        mtime = (
            datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            if exists else ""
        )
        source_status.append({
            "source": name,
            "path": str(path),
            "exists": exists,
            "file_modified_at": mtime,
        })

    all_present = all(item["exists"] for item in source_status)
    decision = "READY_FOR_VALIDATION" if all_present else "INCOMPLETE"

    cycle_id = cycle.strftime("%Y%m%d_%H%M")
    out_dir = Path(args.output_root) / cycle.strftime("%Y-%m-%d") / "cycle_control"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "cycle_id": cycle_id,
        "cycle_start": cycle.strftime("%Y-%m-%d %H:%M:%S"),
        "cycle_end": cycle_end.strftime("%Y-%m-%d %H:%M:%S"),
        "settling_deadline": deadline.strftime("%Y-%m-%d %H:%M:%S"),
        "settling_seconds": args.settling_seconds,
        "max_source_delay_seconds": args.max_source_delay_seconds,
        "decision": decision,
        "sources": source_status,
        "policy": {
            "late_data_not_reassigned": True,
            "raw_files_not_overwritten": True,
            "incomplete_cycles_not_promoted": True,
            "premium_skew_not_calculated": True,
        },
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    output = out_dir / f"cycle_{cycle_id}_decision.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Cycle {cycle_id}: {decision}")
    print(f"Decision file: {output}")


if __name__ == "__main__":
    main()
