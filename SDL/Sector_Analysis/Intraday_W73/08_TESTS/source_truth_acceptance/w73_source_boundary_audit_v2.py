from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import json
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = Path(r"D:\My-data\Share_P&L\Ichart Data\Screenshot")
MONTH = "September26"
DATES = ["2026-09-23", "2026-09-24", "2026-09-25"]
CHECKPOINTS = ["09:45", "10:00", "10:15"]

# Hard safety limits: this stage NEVER opens XLSX files.
MAX_MATCHING_FILES_PER_DAY = 100
MAX_TOTAL_MATCHING_FILES = 300

PATTERN = re.compile(r"_(\d{8})_(\d{6})\.xlsx$", re.I)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_timestamp(path: Path):
    m = PATTERN.search(path.name)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")


def main():
    print("W73 SOURCE BOUNDARY AUDIT V2")
    print("MODE: PATH/FILENAME ONLY — NO XLSX READ — NO CACHE — NO DASHBOARD")
    print(f"PROJECT_ROOT={PROJECT_ROOT}")
    print(f"RAW_ROOT={RAW_ROOT}")
    print(f"MONTH={MONTH}")
    print()

    if not RAW_ROOT.exists():
        print(f"FAIL: RAW_ROOT_NOT_FOUND: {RAW_ROOT}")
        return 2

    month_root = RAW_ROOT / MONTH
    if not month_root.is_dir():
        print(f"FAIL: MONTH_FOLDER_NOT_FOUND: {month_root}")
        return 2

    total = 0
    results = []
    failures = []

    for day in DATES:
        day_root = month_root / day
        print(f"DAY {day}: {day_root}")

        if not day_root.is_dir():
            failures.append(f"{day}: DAY_FOLDER_NOT_FOUND")
            print("  FAIL: day folder missing")
            continue

        # Deliberately non-recursive: only immediate children.
        children = list(day_root.iterdir())
        matching = sorted(
            [p for p in children if p.is_file() and p.name.startswith("Daywise_Price_and_OI_Summary_")
             and p.suffix.lower() == ".xlsx"],
            key=lambda p: parse_timestamp(p) or datetime.max,
        )

        nested_daywise = []
        for child in children:
            if child.is_dir():
                nested_daywise.extend(
                    p for p in child.rglob("Daywise_Price_and_OI_Summary_*.xlsx")
                    if p.is_file()
                )

        if nested_daywise:
            failures.append(f"{day}: NESTED_DAYWISE_FILES_PRESENT")
            print(f"  FAIL: nested Daywise files found: {len(nested_daywise)}")

        if len(matching) > MAX_MATCHING_FILES_PER_DAY:
            failures.append(f"{day}: TOO_MANY_MATCHING_FILES:{len(matching)}")
            print(f"  FAIL: {len(matching)} matching files > limit {MAX_MATCHING_FILES_PER_DAY}")
            continue

        total += len(matching)
        bad_names = [p.name for p in matching if parse_timestamp(p) is None]
        if bad_names:
            failures.append(f"{day}: UNPARSEABLE_TIMESTAMP:{len(bad_names)}")
            print(f"  FAIL: {len(bad_names)} timestamp(s) unparseable")

        print(f"  immediate Daywise XLSX files: {len(matching)}")

        day_result = {"day": day, "folder": str(day_root), "files": len(matching), "checkpoints": []}

        for cp in CHECKPOINTS:
            cutoff = datetime.strptime(f"{day} {cp}", "%Y-%m-%d %H:%M")
            eligible = [p for p in matching if (parse_timestamp(p) is not None and parse_timestamp(p) <= cutoff)]
            future = [p for p in matching if (parse_timestamp(p) is not None and parse_timestamp(p) > cutoff)]

            # Explicit chronological PIT boundary checks.
            if any(parse_timestamp(p) > cutoff for p in eligible):
                failures.append(f"{day} {cp}: FUTURE_FILE_INCLUDED")
            if any(parse_timestamp(p) <= cutoff for p in future):
                failures.append(f"{day} {cp}: CUTOFF_PARTITION_ERROR")

            first = eligible[0].name if eligible else None
            last = eligible[-1].name if eligible else None

            print(f"  {cp}: eligible={len(eligible)} future_excluded={len(future)}")
            print(f"       FIRST={first}")
            print(f"       LAST ={last}")

            day_result["checkpoints"].append({
                "checkpoint": cp,
                "cutoff": cutoff.isoformat(),
                "eligible_count": len(eligible),
                "future_excluded_count": len(future),
                "first_eligible": first,
                "last_eligible": last,
                "eligible_paths": [str(p) for p in eligible],
            })

        results.append(day_result)
        print()

    if total > MAX_TOTAL_MATCHING_FILES:
        failures.append(f"TOTAL_MATCHING_FILES_EXCEEDS_LIMIT:{total}")

    manifest = {
        "audit": "W73_SOURCE_BOUNDARY_AUDIT_V2",
        "mode": "PATH_FILENAME_ONLY",
        "xlsx_opened": False,
        "cache_used": False,
        "dashboard_used": False,
        "raw_source_modified": False,
        "raw_root": str(RAW_ROOT),
        "month": MONTH,
        "dates": DATES,
        "checkpoints": CHECKPOINTS,
        "max_matching_files_per_day": MAX_MATCHING_FILES_PER_DAY,
        "max_total_matching_files": MAX_TOTAL_MATCHING_FILES,
        "total_matching_files": total,
        "failures": failures,
        "results": results,
        "status": "PASS" if not failures else "FAIL",
    }

    out_dir = PROJECT_ROOT / "08_TESTS" / "source_truth_acceptance_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "W73_SOURCE_BOUNDARY_AUDIT_V2.json"
    out_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("========================================")
    print(f"TOTAL MATCHING FILES: {total}")
    print(f"STATUS: {manifest['status']}")
    print(f"MANIFEST: {out_file}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
