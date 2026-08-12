import argparse
from pathlib import Path
from pipeline import process_snapshot

parser = argparse.ArgumentParser(description="Process one SDL intraday snapshot.")
parser.add_argument("file", type=Path)
parser.add_argument("--timestamp", default=None, help="Explicit observation timestamp if filename has no timestamp.")
args = parser.parse_args()

events, _, observed_at = process_snapshot(args.file, args.timestamp)
print(f"Observation: {observed_at}")
print(f"New valid breakouts: {len(events)}")
if not events.empty:
    print(events[["symbol", "current_straddle_premium", "breakout_level"]].to_string(index=False))

