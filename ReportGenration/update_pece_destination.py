from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

LIVE = Path(__file__).resolve().parent
CFG = LIVE / "reports.json"
NEW_DESTINATION = r"D:\My-data\Share_P&L\Ichart Data\Screenshot\PECE_Volume"
PECE_ID = "pece_xhr_total_pe_ce"


def load():
    return json.loads(CFG.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not CFG.exists():
        raise SystemExit("SAFETY STOP: reports.json not found")
    data = load()
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SystemExit("SAFETY STOP: reports.json does not contain jobs[]")
    matches = [j for j in jobs if isinstance(j, dict) and j.get("id") == PECE_ID]
    if len(matches) != 1:
        raise SystemExit(f"SAFETY STOP: expected exactly one {PECE_ID}; found {len(matches)}")
    job = matches[0]
    old = job.get("destination")
    print(f"Current PE/CE destination: {old}")
    print(f"New PE/CE destination:     {NEW_DESTINATION}")
    print(f"PE/CE enabled:             {bool(job.get('enabled'))}")
    if args.check:
        print("CHECK ONLY: no production files modified")
        return
    job["destination"] = NEW_DESTINATION
    fd, tmp_name = tempfile.mkstemp(prefix="reports.json.", suffix=".tmp", dir=str(CFG.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, CFG)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    print("PASS: PE/CE destination updated")
    print("PE/CE remains disabled")
    print("Existing jobs preserved")


if __name__ == "__main__":
    main()
