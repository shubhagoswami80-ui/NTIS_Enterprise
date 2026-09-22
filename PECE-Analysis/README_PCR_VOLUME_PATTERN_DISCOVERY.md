# PCR Volume Pattern Discovery

## Purpose
Processes all `PECE_*.xlsx` files recursively and preserves all source fields.
Each workbook is treated as one cumulative source snapshot. For each workbook,
the latest `Time` row per `Symbol` is retained for interval-wise discovery.

## Outputs
- `Current/pcr_volume_skew_latest.csv`
- `Current/pcr_volume_skew_symbol_profiles.csv`
- `Current/pcr_volume_skew_status.json`
- `History/YYYY-MM-DD/pcr_volume_pattern_all_intervals.csv`
- `Logs/pattern_discovery.log`

## Run
1. Edit `CONFIG.json` if required.
2. Run:
   `python pcr_volume_pattern_discovery.py`

The script does not use price to create bullish or bearish signals. It reports
CE-skew, PE-skew, balanced activity, activity strength, PCR changes, persistence,
and complete interval-wise source observations.
