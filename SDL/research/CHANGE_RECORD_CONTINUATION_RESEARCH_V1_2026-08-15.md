# Change Record — Continuation Research V1

Date: 2026-08-15

Authoritative Git baseline:
`bda7958e4616a611c196df615c95b83e6dc6ea4a`

Commit:
`SDL current authoritative development state`

## Added
`research/continuation_research.py`

## Purpose
Historical evidence study for the future breakout-continuation enhancement.

## Frozen controls
- first 50% event per stock/day;
- later same-day 1x crossing is the primary continuation outcome;
- same-observation 100% is separated;
- unresolved cases remain unresolved;
- features must be point-in-time;
- futures-OI headers are discovered, not assumed;
- no probability;
- no arbitrary weights;
- no production mutation.

## Outputs
- continuation_replay_events.csv
- descriptive_feature_effects.csv
- source_schema_map.csv
- research_summary.csv

## Production status
No production files are changed by this research component.
