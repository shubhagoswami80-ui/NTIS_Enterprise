#!/usr/bin/env python3
"""
Hybrid five-minute alignment layer.

Combines the three supplementary Excel/CSV feeds with an NSE option-chain
file using a common five-minute cycle. It preserves source timestamps and
does not calculate Premium Skew.

Important:
- Source files must represent the same collection cycle.
- File modification time is used only when no timestamp column is available.
- Late or missing sources are marked and are not silently reassigned.
- The output is a combined snapshot only when all required sources are valid.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import json
import pandas as pd


TIME_COLUMNS = [
    "feed_timestamp", "timestamp", "Timestamp", "time", "Time",
    "datetime", "Datetime", "DateTime", "created_at", "collection_time"
]


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=0)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def parse_timestamp(value):
    if pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).to_pydatetime().replace(tzinfo=None)
    except Exception:
        return None


def source_timestamp(df: pd.DataFrame, path: Path) -> tuple[datetime, str]:
    for col in TIME_COLUMNS:
        if col in df.columns:
            values = df[col].dropna()
            if not values.empty:
                parsed = parse_timestamp(values.iloc[0])
                if parsed:
                    return parsed, f"column:{col}"
    return datetime.fromtimestamp(path.stat().st_mtime), "file_mtime"


def cycle_floor(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)


def add_prefix(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    out = df.copy()
    # Preserve common identity fields without prefixing them.
    identity = {"Symbol", "symbol", "Ticker", "ticker", "expiry", "Expiry", "strike", "Strike"}
    rename = {c: f"{prefix}_{c}" for c in out.columns if c not in identity}
    return out.rename(columns=rename)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle-start", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--max-delta-seconds", type=int, default=120)
    ap.add_argument("--daywise", required=True)
    ap.add_argument("--resistance", required=True)
    ap.add_argument("--support-resistance", required=True)
    ap.add_argument("--nse-option-chain", required=True)
    args = ap.parse_args()

    requested = datetime.fromisoformat(args.cycle_start).replace(tzinfo=None)
    cycle = cycle_floor(requested)
    cycle_end = cycle.timestamp() + 300

    inputs = [
        ("daywise", Path(args.daywise)),
        ("resistance", Path(args.resistance)),
        ("support_resistance", Path(args.support_resistance)),
        ("nse", Path(args.nse_option_chain)),
    ]

    frames = []
    source_report = []
    for source, path in inputs:
        record = {
            "source": source,
            "path": str(path),
            "file": path.name,
            "target_cycle": cycle.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if not path.exists():
            record.update(status="MISSING", error="File does not exist")
            source_report.append(record)
            continue

        try:
            df = read_table(path)
            ts, ts_method = source_timestamp(df, path)
            delta = (ts - cycle).total_seconds()
            if delta < 0:
                status = "EARLY_OR_PREEXISTING"
            elif delta <= args.max_delta_seconds:
                status = "VALID"
            else:
                status = "LATE"

            record.update(
                source_timestamp=ts.strftime("%Y-%m-%d %H:%M:%S"),
                timestamp_method=ts_method,
                delta_seconds=round(delta, 1),
                rows=len(df),
                columns=len(df.columns),
                status=status,
            )
            source_report.append(record)

            if status == "VALID":
                frames.append(add_prefix(df, source))
        except Exception as exc:
            record.update(status="READ_ERROR", error=str(exc))
            source_report.append(record)

    statuses = {r["status"] for r in source_report}
    required = {"VALID"}
    ready = len(source_report) == 4 and statuses == required

    out_dir = Path(args.output_root) / cycle.strftime("%Y-%m-%d") / "synchronized"
    out_dir.mkdir(parents=True, exist_ok=True)
    cycle_id = cycle.strftime("%Y%m%d_%H%M")

    manifest = {
        "cycle_id": cycle_id,
        "target_cycle": cycle.strftime("%Y-%m-%d %H:%M:%S"),
        "cycle_interval_seconds": 300,
        "max_delta_seconds": args.max_delta_seconds,
        "ready_for_combined_analysis": ready,
        "source_report": source_report,
        "policy": {
            "all_four_sources_required": True,
            "late_data_not_reassigned": True,
            "raw_sources_untouched": True,
            "premium_skew_not_calculated_here": True,
        },
    }

    manifest_path = out_dir / f"aligned_{cycle_id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pd.DataFrame(source_report).to_csv(
        out_dir / f"aligned_{cycle_id}_source_report.csv", index=False
    )

    if ready and frames:
        combined = frames[0]
        # Conservative outer merge: do not discard rows from any source.
        # Identity-based joining is intentionally deferred because the three
        # supplementary files may have different row granularities.
        for frame in frames[1:]:
            combined = pd.concat([combined, frame], ignore_index=True, sort=False)
        combined.insert(0, "target_cycle", cycle.strftime("%Y-%m-%d %H:%M:%S"))
        combined.insert(1, "alignment_status", "ALIGNED")
        combined.to_csv(out_dir / f"aligned_{cycle_id}_combined.csv", index=False)
        print("Combined snapshot created.")
    else:
        print("Combined snapshot NOT created: source set is incomplete or misaligned.")

    print(f"Manifest: {manifest_path}")
    print(f"Ready: {ready}")


if __name__ == "__main__":
    main()
